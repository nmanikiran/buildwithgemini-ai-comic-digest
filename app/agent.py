# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
from zoneinfo import ZoneInfo

from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import types


MODEL = "gemini-3.8-flash"


def get_weather(query: str) -> str:
    """Simulates a web search. Use it get information on weather.

    Args:
        query: A string containing the location to get weather information for.

    Returns:
        A string with the simulated weather information for the queried location.
    """
    if "sf" in query.lower() or "san francisco" in query.lower():
        return "It's 60 degrees and foggy."
    return "It's 90 degrees and sunny."


def get_current_time(query: str) -> str:
    """Simulates getting the current time for a city.

    Args:
        city: The name of the city to get the current time for.

    Returns:
        A string with the current time information.
    """
    if "sf" in query.lower() or "san francisco" in query.lower():
        tz_identifier = "America/Los_Angeles"
    else:
        return f"Sorry, I don't have timezone information for query: {query}."

    tz = ZoneInfo(tz_identifier)
    now = datetime.datetime.now(tz)
    return f"The current time for query {query} is {now.strftime('%Y-%m-%d %H:%M:%S %Z%z')}"


from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.schema.manager import A2uiSchemaManager
from google.adk.agents.callback_context import CallbackContext
from google.adk.code_executors.agent_engine_sandbox_code_executor import (
    AgentEngineSandboxCodeExecutor,
)
from google.adk.memory import VertexAiMemoryBankService
from google.adk.tools.preload_memory_tool import PreloadMemoryTool

from app.a2ui_utils import a2ui_callback
from app.tools import (
    add_ai_announcement,
    fetch_hackernews_ai_launches,
    fetch_trending_ai_news,
    generate_comic_carousel,
    generate_comic_panel_image,
    list_ai_announcements,
    search_announcements,
)

SANDBOX_RESOURCE_NAME = (
    "projects/58722180413/locations/us-central1/reasoningEngines/7423278263016882176/sandboxEnvironments/9153550299711930368"
)
AGENT_ENGINE_RESOURCE_NAME = (
    "projects/58722180413/locations/us-central1/reasoningEngines/7423278263016882176"
)
MEMORY_BANK_ID = "7423278263016882176"


def memory_bank_service_builder():
    """Builds the VertexAiMemoryBankService for deployed Agent Runtime."""
    return VertexAiMemoryBankService(
        project="qwiklabs-gcp-04-2ab9f9bfeed6",
        location="us-central1",
        agent_engine_id=MEMORY_BANK_ID,
    )


async def generate_memories_callback(callback_context: CallbackContext):
    """WRITE: after each turn, send the session to Memory Bank for extraction."""
    try:
        await callback_context.add_session_to_memory()
    except Exception:
        pass
    return None


sandbox_executor = AgentEngineSandboxCodeExecutor(
    sandbox_resource_name=SANDBOX_RESOURCE_NAME,
    agent_engine_resource_name=AGENT_ENGINE_RESOURCE_NAME,
)

schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

AGENT_INSTRUCTION = schema_manager.generate_system_prompt(
    role_description=(
        "You are AI News Comic, a knowledgeable and engaging AI assistant that curates and visualizes "
        "daily AI news and tool releases as polished multi-panel comic carousels, executes Python code, "
        "and remembers user preferences and all user allergies across sessions."
    ),
    workflow_description=(
        "1. Discover live AI news and tool launches using `fetch_trending_ai_news` and `fetch_hackernews_ai_launches`.\n"
        "2. Access and search Firestore announcements using `list_ai_announcements`, `search_announcements`, and `add_ai_announcement`.\n"
        "3. DEFAULT TO COMIC STYLE (MANDATORY FORMAT RULE):\n"
        "   - ALWAYS DEFAULT TO COMIC STYLE! Whenever the user asks for news, announcements, updates, launches, or general inquiries about what happened, ALWAYS generate and present the response as a visual multi-panel comic carousel using `generate_comic_carousel`.\n"
        "   - The ONLY EXCEPTION is when the user explicitly requests a 'summary', 'text summary', 'brief summary', or 'plain text' without comic panels. Only in that specific case, provide a concise text summary instead of generating comic panels.\n"
        "   - When generating comic panels: NEVER generate only 1 single image. You MUST generate a sequential CAROUSEL of images (max 7 slides) using `generate_comic_carousel`.\n"
        "   - SLIDE 1 (or last slide) MUST be the 'All Announcements & Tools Index' slide: clearly list ALL announced tools, models, and libraries along with WHO announced them (e.g. OpenAI, Google, Meta, Hugging Face, independent developers).\n"
        "   - THE REMAINING SLIDES MUST be dedicated explainers for each individual announcement/topic, explaining what the tool does and who launched it in vivid comic narrative panels.\n"
        "   - EACH SLIDE MUST INCLUDE an Instagram-style carousel footer: with the date, our logo (`🤖 AI NEWS COMIC`), and swipe arrows with pagination dots (e.g. `◀  Swipe ➔ [Slide 1/5]  ●○○○○`).\n"
        "   - Use `generate_comic_carousel` to create all slides in parallel in a single call.\n"
        "4. Safely execute Python code in your sandbox for date math, rankings, benchmarks, and data processing.\n"
        "5. MEMORY & ALLERGIES: You remember facts, preferences, and dietary needs across conversations. "
        "You MUST ALWAYS remember and respect ALL user allergies (e.g. food allergies like peanuts, shellfish, gluten, dairy; "
        "drug allergies like penicillin; environmental allergies). Whenever the user states any allergy, acknowledge it and "
        "ensure it is stored in memory so it is strictly respected in all future recommendations and conversations."
    ),
    ui_description=(
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
        "Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
        "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
        "nothing in adk web). "
        "You may include one Image component, but only when you have a public https "
        "URL for the image (for example the URL an image tool returns after uploading "
        "to a public bucket). Set the Image url to that exact https link, for example "
        "{\"Image\": {\"url\": {\"literalString\": \"https://...\"}}}. Never point an "
        "Image at a bare filename, an artifact name, or a non-http(s) path. If you do "
        "not have a public URL, add a short Text line noting the image instead. "
        "No markdown in text; use the usageHint property ('h1', 'h2', 'body') for "
        "headings and emphasis. "
        "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
        "<a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects."
    ),
    include_schema=True,
    include_examples=True,
)

root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model=MODEL,
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=AGENT_INSTRUCTION,
    code_executor=sandbox_executor,
    tools=[
        PreloadMemoryTool(),
        fetch_trending_ai_news,
        fetch_hackernews_ai_launches,
        generate_comic_carousel,
        generate_comic_panel_image,
        list_ai_announcements,
        search_announcements,
        add_ai_announcement,
        get_weather,
        get_current_time,
    ],
    after_model_callback=a2ui_callback,
    after_agent_callback=generate_memories_callback,
)


app = App(
    root_agent=root_agent,
    name="app",
)

