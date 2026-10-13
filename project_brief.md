# My agent: ai-news-comic (AI News Comic)
One-liner: A conversational agent that helps tech enthusiasts and developers catch up on daily AI news with a catalog of curated announcements, defaulting to a visual multi-panel comic carousel (with a dedicated tools & creators showcase slide), unless a summary is requested.

Tool coverage:
- Memory: User preferences for AI topics (LLMs, vision, robotics, open-source), favorite companies/labs, and reading history to prevent duplicate stories
- Tools: Look up / fetch recent AI news, model drops, and tool releases
- Catalog/UI: Curated list of daily news stories and newly announced tools rendered as rich cards and comparison tables
- Image gen: Up to 7 sequential comic-style panel images (visual story slides + 1 chapter/slide highlighting all announced tools and who released them)
- Sandbox: Date calculation, tool ranking, and release timeline formatting

Recommended for every project: memory, storage, tools, image generation, A2UI
Agent-specific / stretch (pick what fits): code sandbox for timeline formatting, Cloud Trace, video generation with Omni

Storage bucket:
- gs://ai-comic-digest-media-qwiklabs-gcp-04-2ab9f9bfeed6 (public read enabled for embedding web images)
