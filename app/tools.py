"""Firestore, news, and image generation function tools for ai-comic-digest."""

from typing import Any
from google import genai
from google.adk.tools import ToolContext
from google.cloud import firestore, storage
from google.genai import types

PROJECT_ID = "qwiklabs-gcp-04-2ab9f9bfeed6"
COLLECTION_NAME = "ai_announcements"
BUCKET_NAME = "ai-comic-digest-media-qwiklabs-gcp-04-2ab9f9bfeed6"
IMAGE_MODEL = "gemini-3.1-flash-lite-image"
IMAGE_LOCATION = "global"


def _get_firestore_client() -> firestore.Client:
    """Returns a Firestore client initialized with the hardcoded project ID."""
    return firestore.Client(project=PROJECT_ID)


def list_ai_announcements(category: str = "", limit: int = 10) -> str:
    """Lists recent AI news announcements and tool releases from Firestore.

    Args:
        category: Optional category filter (e.g. 'Model Release', 'Open Source', 'Autonomous Agents', 'Infrastructure').
                  Leave empty to list all categories.
        limit: Maximum number of announcements to return (default 10).

    Returns:
        A formatted summary of announcements including titles, who announced them,
        announced tools/models, dates, and summaries.
    """
    db = _get_firestore_client()
    query = db.collection(COLLECTION_NAME)

    if category:
        query = query.where(filter=firestore.FieldFilter("category", "==", category))

    docs = list(query.limit(limit).stream())
    if not docs:
        if category:
            return f"No announcements found for category '{category}'."
        return "No announcements found in the database."

    results = []
    for doc in docs:
        data = doc.to_dict()
        tools_str = ", ".join(data.get("tools_announced", [])) or "None specified"
        results.append(
            f"• Title: {data.get('title', 'Untitled')}\n"
            f"  Announced By: {data.get('announced_by', 'Unknown')}\n"
            f"  Tools/Models: {tools_str}\n"
            f"  Category: {data.get('category', 'General')}\n"
            f"  Date: {data.get('date', 'Unknown')}\n"
            f"  Summary: {data.get('summary', 'No summary provided')}\n"
            f"  URL: {data.get('url', 'N/A')}"
        )

    return "\n\n".join(results)


def search_announcements(keyword: str) -> str:
    """Searches AI news announcements by company name, tool name, or keyword.

    Args:
        keyword: The company name, model name, or topic to search for (e.g. 'Google', 'Anthropic', 'Llama', 'Operator').

    Returns:
        A formatted list of matching announcements.
    """
    if not keyword:
        return list_ai_announcements(limit=5)

    db = _get_firestore_client()
    docs = list(db.collection(COLLECTION_NAME).stream())

    keyword_lower = keyword.lower()
    matches = []

    for doc in docs:
        data = doc.to_dict()
        title = data.get("title", "").lower()
        announced_by = data.get("announced_by", "").lower()
        summary = data.get("summary", "").lower()
        tools = [t.lower() for t in data.get("tools_announced", [])]
        category = data.get("category", "").lower()

        if (
            keyword_lower in title
            or keyword_lower in announced_by
            or keyword_lower in summary
            or keyword_lower in category
            or any(keyword_lower in t for t in tools)
        ):
            tools_str = ", ".join(data.get("tools_announced", [])) or "None specified"
            matches.append(
                f"• Title: {data.get('title', 'Untitled')}\n"
                f"  Announced By: {data.get('announced_by', 'Unknown')}\n"
                f"  Tools/Models: {tools_str}\n"
                f"  Category: {data.get('category', 'General')}\n"
                f"  Date: {data.get('date', 'Unknown')}\n"
                f"  Summary: {data.get('summary', 'No summary provided')}\n"
                f"  URL: {data.get('url', 'N/A')}"
            )

    if not matches:
        return f"No announcements found matching '{keyword}'."

    return "\n\n".join(matches)


def add_ai_announcement(
    title: str,
    summary: str,
    announced_by: str,
    tools_announced: list[str],
    category: str = "General",
    date: str = "",
    url: str = "",
) -> str:
    """Adds a new AI announcement or tool release to Firestore.

    Args:
        title: The headline or title of the announcement.
        summary: A human-like plain summary of the release.
        announced_by: The organization, company, or individual author.
        tools_announced: List of specific tools, models, or libraries announced.
        category: The category (e.g., 'Model Release', 'Framework', 'Autonomous Agents', 'Open Source').
        date: The announcement date (e.g., '2026-10-13').
        url: Reference URL or link.

    Returns:
        A confirmation message with the generated document ID.
    """
    db = _get_firestore_client()
    import re
    # Generate a slug id
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", f"{announced_by}-{title}".lower()).strip("-")[:50]
    doc_id = slug or None

    item_data = {
        "title": title,
        "summary": summary,
        "announced_by": announced_by,
        "tools_announced": tools_announced,
        "category": category,
        "date": date,
        "url": url,
    }

    if doc_id:
        item_data["id"] = doc_id
        db.collection(COLLECTION_NAME).document(doc_id).set(item_data)
        saved_id = doc_id
    else:
        _, doc_ref = db.collection(COLLECTION_NAME).add(item_data)
        saved_id = doc_ref.id

    return f"Successfully saved announcement '{title}' by {announced_by} (ID: {saved_id}) into Firestore."


def fetch_trending_ai_news(limit: int = 5) -> str:
    """Fetches real-time trending AI research papers, model releases, and tool announcements from Hugging Face Daily Papers.

    Args:
        limit: Number of trending announcements to retrieve (default 5, max 10).

    Returns:
        A formatted list of current AI announcements including title, authors, summary, and link.
    """
    import json
    import urllib.request

    url = "https://huggingface.co/api/daily_papers"
    req = urllib.request.Request(url, headers={"User-Agent": "AIComicDigest/1.0"})

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception as e:
        return f"Error fetching live AI news: {e}"

    if not data:
        return "No trending AI papers found today."

    items = []
    for entry in data[: min(limit, 10)]:
        paper = entry.get("paper", {})
        title = paper.get("title", "Untitled")
        paper_id = paper.get("id", "")
        summary = paper.get("summary", "").replace("\n", " ")
        if len(summary) > 200:
            summary = summary[:197] + "..."
        authors = [a.get("name", "") for a in paper.get("authors", [])[:3]]
        authors_str = ", ".join(authors) if authors else "Unknown"
        paper_url = f"https://huggingface.co/papers/{paper_id}" if paper_id else "N/A"

        items.append(
            f"• Title: {title}\n"
            f"  Announced / Authored By: {authors_str}\n"
            f"  Summary: {summary}\n"
            f"  Link: {paper_url}"
        )

    return "\n\n".join(items)


def fetch_hackernews_ai_launches(query: str = "Show HN AI", limit: int = 5) -> str:
    """Fetches live AI tool announcements and community releases from Hacker News (indexed in public-apis).

    Args:
        query: Search term for AI releases (e.g. 'Show HN AI', 'AI agent', 'LLM tool'). Defaults to 'Show HN AI'.
        limit: Maximum number of launches to return (default 5, max 10).

    Returns:
        A formatted list of real-time community AI tool launches, who released them, community score, and link.
    """
    import json
    import os
    import urllib.parse
    import urllib.request

    api_key = os.getenv("HACKERNEWS_API_KEY", "")
    params = urllib.parse.urlencode({
        "query": query,
        "tags": "story",
        "hitsPerPage": min(limit, 10),
    })
    url = f"https://hn.algolia.com/api/v1/search_by_date?{params}"

    headers = {"User-Agent": "AIComicDigest/1.0"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception as e:
        return f"Error querying Hacker News API: {e}"

    hits = data.get("hits", [])
    if not hits:
        return f"No AI releases found on Hacker News for query '{query}'."

    results = []
    for hit in hits:
        title = hit.get("title", "Untitled")
        author = hit.get("author", "Anonymous")
        points = hit.get("points", 0)
        url_link = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}"

        results.append(
            f"• Tool / Release: {title}\n"
            f"  Announced By: {author}\n"
            f"  Community Points: {points}\n"
            f"  Project URL: {url_link}"
        )

    return "\n\n".join(results)


async def generate_comic_panel_image(prompt: str, tool_context: ToolContext = None) -> str:
    """Generates a comic-style panel image or tool showcase slide for an AI announcement using gemini-3.1-flash-lite-image in the global region.

    Saves the image artifact to the Playground and uploads the image bytes directly to Cloud Storage.

    Args:
        prompt: Detailed visual prompt describing the comic panel scene, characters, caption, or tool showcase slide.

    Returns:
        The public HTTPS URL of the uploaded image.
    """
    import inspect
    import time
    import uuid

    client = genai.Client(vertexai=True, project=PROJECT_ID, location=IMAGE_LOCATION)
    response = await client.aio.models.generate_content(
        model=IMAGE_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
        ),
    )

    candidate = response.candidates[0] if response.candidates else None
    if not candidate or not candidate.content or not candidate.content.parts:
        return "Error: Model did not return an image."

    part = candidate.content.parts[0]
    if not part.inline_data or not part.inline_data.data:
        return "Error: No inline image data found in model response."

    image_bytes = part.inline_data.data
    mime_type = part.inline_data.mime_type or "image/jpeg"
    ext = "jpg" if "jpeg" in mime_type else "png"
    timestamp = int(time.time())
    unique_id = uuid.uuid4().hex[:8]
    filename = f"comic_panel_{timestamp}_{unique_id}.{ext}"

    if tool_context is not None:
        try:
            res = tool_context.save_artifact(filename, part)
            if inspect.isawaitable(res):
                await res
        except Exception:
            pass

    import asyncio

    storage_client = storage.Client(project=PROJECT_ID)
    bucket = storage_client.bucket(BUCKET_NAME)
    object_name = f"comic_panels/{filename}"
    blob = bucket.blob(object_name)
    await asyncio.to_thread(blob.upload_from_string, image_bytes, content_type=mime_type)

    public_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{object_name}"
    return public_url


async def generate_comic_carousel(
    slides: list[dict],
    digest_date: str = "",
    tool_context: ToolContext = None,
) -> str:
    """Generates a multi-slide polished comic carousel (max 7 slides) for daily AI news in parallel.

    Generates all slide images concurrently using gemini-3.1-flash-lite-image in the global region,
    saves each image as an artifact, uploads each to Cloud Storage, and returns formatted
    Instagram-style carousel slides with date, AI Comic Digest logo, and swipe arrows.

    Args:
        slides: List of slide objects (up to 7 slides). Each item should contain:
            - slide_number (int): 1-indexed order (1, 2, ...).
            - title (str): Catchy slide title (e.g. 'All Tools Launch Board', 'Claude 3.7 Reasoning Explainer').
            - slide_type (str): 'index' (for the all-tools overview slide) or 'explainer' (for topic deep-dives).
            - prompt (str): Visual prompt for comic illustration with bold inks, characters, and scene details.
            - caption (str): Narrative storyline caption explaining the scene or tools.
            - announced_by (str, optional): Creator / company behind the tools featured.
        digest_date: Optional date string for the footer (e.g. 'October 13, 2026'). Defaults to today.

    Returns:
        A rich Markdown representation of the Instagram-style comic carousel with embedded images,
        captions, tool attributions, and navigation swipe footers.
    """
    import asyncio
    import datetime
    import inspect
    import json
    import time
    import uuid

    if isinstance(slides, str):
        try:
            slides = json.loads(slides)
        except Exception:
            pass

    if not isinstance(slides, list) or not slides:
        return "Error: slides must be a non-empty list of slide descriptions."

    slides = slides[:7]
    total_slides = len(slides)

    if not digest_date:
        digest_date = datetime.date.today().strftime("%B %d, %Y")

    client = genai.Client(vertexai=True, project=PROJECT_ID, location=IMAGE_LOCATION)
    storage_client = storage.Client(project=PROJECT_ID)
    bucket = storage_client.bucket(BUCKET_NAME)

    async def _generate_slide(slide_info: dict, index: int) -> dict:
        slide_num = slide_info.get("slide_number", index + 1)
        title = slide_info.get("title", f"Slide {slide_num}")
        slide_type = slide_info.get("slide_type", "explainer" if index > 0 else "index")
        user_prompt = slide_info.get("prompt", "")
        caption = slide_info.get("caption", "")
        announced_by = slide_info.get("announced_by", "")

        # Enhance prompt for comic art quality
        if slide_type == "index":
            styled_prompt = (
                "Polished comic book cover / splash page marquee poster. "
                "Title text style: 'AI NEWS COMIC — TODAY'S RELEASES'. "
                "Vibrant retro-futuristic comic illustration showing a dynamic showcase board or glowing neon marquee "
                "listing today's AI tools and creator logos. Bold ink outlines, halftone dot textures, dramatic lighting: "
                + user_prompt
            )
        else:
            styled_prompt = (
                "Polished dynamic comic book panel with bold graphic ink line art, action lines, expressive characters, "
                "vivid retro-modern palette, narrative caption box, and sound effects: "
                + user_prompt
            )

        timestamp = int(time.time())
        unique_id = uuid.uuid4().hex[:8]
        filename = f"carousel_slide_{slide_num}_{timestamp}_{unique_id}.jpg"

        try:
            response = await client.aio.models.generate_content(
                model=IMAGE_MODEL,
                contents=styled_prompt,
                config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
            )
            candidate = response.candidates[0] if response.candidates else None
            part = candidate.content.parts[0] if candidate and candidate.content else None

            if part and part.inline_data and part.inline_data.data:
                image_bytes = part.inline_data.data
                mime_type = part.inline_data.mime_type or "image/jpeg"

                # Save artifact to Playground
                if tool_context is not None:
                    try:
                        res = tool_context.save_artifact(filename, part)
                        if inspect.isawaitable(res):
                            await res
                    except Exception:
                        pass

                # Upload to GCS
                object_name = f"comic_panels/{filename}"
                blob = bucket.blob(object_name)
                await asyncio.to_thread(blob.upload_from_string, image_bytes, content_type=mime_type)
                public_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{object_name}"
            else:
                public_url = ""
        except Exception as e:
            public_url = f"Error generating image: {e}"

        return {
            "slide_number": slide_num,
            "title": title,
            "slide_type": slide_type,
            "image_url": public_url,
            "caption": caption,
            "announced_by": announced_by,
        }

    # Generate all slides concurrently in parallel
    results = await asyncio.gather(*[_generate_slide(s, i) for i, s in enumerate(slides)])

    # Build Instagram carousel markdown
    rendered_output = []
    for r in results:
        num = r["slide_number"]
        dots = "".join("●" if i + 1 == num else "○" for i in range(total_slides))
        if num == 1:
            swipe_text = f"◀ Swipe ➔ [{num}/{total_slides}]  {dots}"
        elif num == total_slides:
            swipe_text = f"◀ Swipe Back [{num}/{total_slides}]  {dots} • End of Carousel"
        else:
            swipe_text = f"◀ Swipe ➔ [{num}/{total_slides}]  {dots}"

        slide_lines = [
            f"### 📸 [SLIDE {num}/{total_slides}] {r['title']}",
        ]
        if r["image_url"] and not r["image_url"].startswith("Error"):
            slide_lines.append(f"![{r['title']}]({r['image_url']})")

        if r["slide_type"] == "index":
            slide_lines.append("**🌟 All Announced Tools & Creators Showcase:**")
        elif r["announced_by"]:
            slide_lines.append(f"**⚡ Announced By:** {r['announced_by']}")

        if r["caption"]:
            slide_lines.append(f"\n{r['caption']}")

        slide_lines.append(
            f"\n> 📅 {digest_date}  •  🤖 **AI NEWS COMIC**  •  {swipe_text}\n"
        )
        rendered_output.append("\n".join(slide_lines))

    return "\n\n---\n\n".join(rendered_output)

