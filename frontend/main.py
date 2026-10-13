"""Minimal FastAPI proxy for a deployed A2A agent (Agent Runtime, agents-cli 1.1.0+).

The browser talks ONLY to this proxy (same origin, no CORS, no GCP creds in the
browser). The proxy authenticates with Application Default Credentials and
forwards chat to the deployed agent over the A2A protocol, returning replies as
structured parts the chat UI knows how to show:

  * {"kind": "text", "text": ...}  -> a normal chat bubble
  * {"kind": "a2ui", "data": ...}  -> one A2UI message (beginRendering /
    surfaceUpdate); static/index.html renders these as a card.

Why A2A: agents-cli 1.1.0 (GA) deploys ADK agents to Agent Runtime as A2A agents
and no longer registers the reasoning-engine operation schema the old
`agent_engines.get(...).stream_query()` path relied on (operation_schemas() comes
back empty). The container serves the A2A protocol over the Agent Engine HTTP
passthrough, so this proxy fetches the agent's card and sends messages with the
a2a-sdk client (the same path `agents-cli run --mode a2a` uses). This works for
both A2A and plain ADK 1.1.0 deployments (the container serves A2A either way).

Run:
  pip install -r requirements.txt
  export AGENT_ENGINE_RESOURCE_NAME="projects/.../locations/.../reasoningEngines/..."
  export AGENT_DIRECTORY="app"   # your agent's app directory (agents-cli-manifest.yaml)
  python main.py                 # -> http://localhost:8080
"""

import os
import uuid

import google.auth
import google.auth.transport.requests
import httpx
from a2a.client import ClientConfig, ClientFactory
try:
    from a2a.types import (
        AgentCard,
        FilePart,
        Message,
        Part,
        Role,
        TaskArtifactUpdateEvent,
        TextPart,
        TransportProtocol,
    )
except ImportError:
    from a2a.compat.v0_3.types import (
        AgentCard,
        FilePart,
        Message,
        Part,
        Role,
        TaskArtifactUpdateEvent,
        TextPart,
        TransportProtocol,
    )
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

import json
from pathlib import Path

# Load .env if present
env_file = Path(__file__).parent / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

RESOURCE = os.environ.get("AGENT_ENGINE_RESOURCE_NAME")
if not RESOURCE:
    meta_path = Path(__file__).resolve().parent.parent / "deployment_metadata.json"
    if meta_path.exists():
        with open(meta_path) as f:
            RESOURCE = json.load(f).get("remote_agent_runtime_id", "")

if not RESOURCE:
    raise KeyError("AGENT_ENGINE_RESOURCE_NAME environment variable is required")

# The agent's app directory (matches agent_directory in agents-cli-manifest.yaml).
AGENT_DIRECTORY = os.environ.get("AGENT_DIRECTORY", "app")
# Location is embedded in the resource name: projects/<p>/locations/<loc>/reasoningEngines/<id>.
LOCATION = RESOURCE.split("/locations/")[1].split("/")[0]

# A2A endpoint for an Agent Runtime deployment, via the Agent Engine HTTP
# passthrough. The card lives at the well-known path under this base.
A2A_BASE = (
    f"https://{LOCATION}-aiplatform.googleapis.com/reasoningEngines/v1/"
    f"{RESOURCE}/api/a2a/{AGENT_DIRECTORY}"
)
A2A_CARD_URL = f"{A2A_BASE}/.well-known/agent-card.json"

# The agent tags its A2UI data parts with this mime type.
_A2UI_MIME = "application/json+a2ui"

# One set of ADC credentials, refreshed per request (access tokens expire ~1h).
_creds, _ = google.auth.default(
    scopes=["https://www.googleapis.com/auth/cloud-platform"]
)


def _auth_headers() -> dict[str, str]:
    _creds.refresh(google.auth.transport.requests.Request())
    return {
        "Authorization": f"Bearer {_creds.token}",
        "Content-Type": "application/json",
    }


app = FastAPI()


@app.exception_handler(Exception)
async def _json_errors(request: Request, exc: Exception):
    # Always return JSON so the browser never receives a plain-text 500 page
    # (which shows up in the chat as "Unexpected token 'I', "Internal S"... is
    # not valid JSON"). Any server-side failure now surfaces as a readable
    # message in the chat bubble instead.
    return JSONResponse(
        status_code=200,
        content={
            "parts": [{"kind": "text", "text": f"Error: {type(exc).__name__}: {exc}"}]
        },
    )


# Reuse ONE A2A context per user so the agent remembers the conversation.
_contexts: dict[str, str] = {}
# Cache the agent card after the first fetch.
_card: AgentCard | None = None


async def _get_card(client: httpx.AsyncClient) -> AgentCard:
    global _card
    if _card is None:
        resp = await client.get(A2A_CARD_URL)
        resp.raise_for_status()
        card = AgentCard(**resp.json())
        # Agent Runtime does not serve a public card URL, so point the client at
        # the passthrough base for message sends.
        card.url = A2A_BASE
        _card = card
    return _card


def _extract_parts(parts: list) -> list[dict]:
    """Turn A2A response parts into structured parts for the chat UI.

    Text parts pass through as {"kind": "text"}. A2UI data parts (tagged
    application/json+a2ui) become {"kind": "a2ui", "data": <message>} so the UI
    renders the card; each data part is one A2UI message (beginRendering or
    surfaceUpdate).
    """
    out: list[dict] = []
    for p in parts:
        root = getattr(p, "root", p)
        # 1. Text parts
        if hasattr(root, "text") and root.text:
            raw_text = str(root.text)
            # Extract any embedded a2ui-json or a2a_datapart_json blocks
            a2ui_matches = re.findall(
                r"<(?:a2ui-json|a2a_datapart_json)>(.*?)</(?:a2ui-json|a2a_datapart_json)>",
                raw_text,
                re.DOTALL,
            )
            clean_text = re.sub(
                r"<(?:a2ui-json|a2a_datapart_json)>.*?</(?:a2ui-json|a2a_datapart_json)>",
                "",
                raw_text,
                flags=re.DOTALL,
            ).strip()
            if clean_text:
                out.append({"kind": "text", "text": clean_text})
            for m in a2ui_matches:
                try:
                    parsed = json.loads(m.strip())
                    if isinstance(parsed, list):
                        for item in parsed:
                            if isinstance(item, dict):
                                out.append({"kind": "a2ui", "data": item})
                    elif isinstance(parsed, dict):
                        out.append({"kind": "a2ui", "data": parsed})
                except Exception:
                    pass
            continue

        # 2. Data parts (A2UI)
        data_payload = getattr(root, "data", root)
        if isinstance(data_payload, dict):
            meta = data_payload.get("metadata") or getattr(root, "metadata", None) or {}
            mime = meta.get("mimeType") if isinstance(meta, dict) else None
            inner_data = data_payload.get("data", data_payload)
            if mime == _A2UI_MIME or (
                isinstance(inner_data, dict)
                and any(
                    k in inner_data
                    for k in ("beginRendering", "surfaceUpdate", "deleteSurface")
                )
            ):
                out.append({"kind": "a2ui", "data": inner_data})
                continue
            if mime == "text/plain" and "text" in data_payload:
                out.append({"kind": "text", "text": data_payload["text"]})
                continue

        # 3. File parts
        if isinstance(root, FilePart) or hasattr(root, "file"):
            file_obj = getattr(root, "file", None)
            uri = getattr(file_obj, "uri", None) if file_obj else None
            if uri:
                out.append({"kind": "text", "text": uri})
                continue

        if isinstance(data_payload, str) and data_payload:
            out.append({"kind": "text", "text": data_payload})
    return out


@app.post("/chat")
async def chat(req: Request):
    body = await req.json()
    message = body.get("message", "")
    user_id = body.get("user_id") or "web-user"
    parts: list[dict] = []

    async with httpx.AsyncClient(headers=_auth_headers(), timeout=120) as client:
        card = await _get_card(client)
        factory = ClientFactory(
            ClientConfig(
                supported_transports=[
                    TransportProtocol.jsonrpc,
                    TransportProtocol.http_json,
                ],
                httpx_client=client,
            )
        )
        a2a_client = factory.create(card)

        msg = Message(
            message_id=str(uuid.uuid4()),
            role=Role.user,
            parts=[Part(root=TextPart(text=message))],
            context_id=_contexts.get(user_id),
        )

        last_task = None
        got_artifact_update = False
        async for event in a2a_client.send_message(msg):
            if not isinstance(event, tuple):
                continue
            task, update = event
            if task is not None:
                last_task = task
                if getattr(task, "context_id", None):
                    _contexts[user_id] = task.context_id
            if isinstance(update, TaskArtifactUpdateEvent):
                got_artifact_update = True
                parts.extend(_extract_parts(update.artifact.parts))
            elif hasattr(update, "status") and update.status:
                status_msg = getattr(update.status, "message", None)
                if status_msg and getattr(status_msg, "parts", None):
                    parts.extend(_extract_parts(status_msg.parts))

        # Non-streaming fallback: pull parts from the final task's artifacts.
        if not got_artifact_update and last_task is not None:
            for artifact in getattr(last_task, "artifacts", None) or []:
                parts.extend(_extract_parts(artifact.parts))

        # Check task history for any text replies or comic carousel markdown
        if last_task is not None and getattr(last_task, "history", None):
            has_comic_text = any(
                p.get("kind") == "text" and "SLIDE" in p.get("text", "")
                for p in parts
            )
            if not has_comic_text:
                for hist_msg in reversed(last_task.history):
                    if getattr(hist_msg, "role", None) == Role.agent:
                        for p in getattr(hist_msg, "parts", []):
                            root = getattr(p, "root", p)
                            data = getattr(root, "data", None)
                            if isinstance(data, dict):
                                resp = data.get("response")
                                if isinstance(resp, dict):
                                    res_str = resp.get("result")
                                    if isinstance(res_str, str) and "SLIDE" in res_str:
                                        parts.insert(0, {"kind": "text", "text": res_str})
                                        has_comic_text = True
                                        break
                            elif hasattr(root, "text") and root.text and "SLIDE" in str(root.text):
                                parts.insert(0, {"kind": "text", "text": str(root.text)})
                                has_comic_text = True
                                break
                    if has_comic_text:
                        break

    if not parts:
        # The turn produced no text or UI (e.g. the agent only ran tools, or a
        # tool stalled). Be honest rather than silent.
        parts = [{"kind": "text", "text": "(The agent didn't return a reply.)"}]
    return JSONResponse({"parts": parts})


# Serve the chat UI (keep this mount last so /chat wins).
_static_dir = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=str(_static_dir), html=True), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
