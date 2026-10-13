"""Seed Firestore with initial AI news announcements for ai-comic-digest."""

from google.cloud import firestore

PROJECT_ID = "qwiklabs-gcp-04-2ab9f9bfeed6"
COLLECTION_NAME = "ai_announcements"

SAMPLE_ANNOUNCEMENTS = [
    {
        "id": "google-gemini-3-8-flash",
        "title": "Gemini 3.8 Flash & Agent Development Kit 2.6 Released",
        "summary": "Google introduced Gemini 3.8 Flash featuring sub-second agentic reasoning alongside ADK 2.6 with built-in A2A protocols and Memory Bank integration.",
        "tools_announced": ["Gemini 3.8 Flash", "ADK 2.6", "Agent Platform Memory Bank"],
        "announced_by": "Google DeepMind",
        "category": "Model & Framework",
        "date": "2026-10-12",
        "url": "https://deepmind.google/technologies/gemini/",
    },
    {
        "id": "anthropic-claude-3-7-sonnet",
        "title": "Claude 3.7 Sonnet Hybrid Reasoning Model",
        "summary": "Anthropic announced Claude 3.7 Sonnet with a hybrid architecture combining rapid standard responses with deep, controllable chain-of-thought thinking.",
        "tools_announced": ["Claude 3.7 Sonnet", "Extended Thinking API"],
        "announced_by": "Anthropic",
        "category": "Model Release",
        "date": "2026-10-12",
        "url": "https://www.anthropic.com/news/claude-3-7-sonnet",
    },
    {
        "id": "openai-operator-autonomous-agent",
        "title": "OpenAI Unveils Operator for Autonomous GUI Workflows",
        "summary": "OpenAI previewed Operator, an agent system capable of executing complex web navigation and browser tasks directly from natural language requests.",
        "tools_announced": ["Operator", "Computer-Using Agent SDK"],
        "announced_by": "OpenAI",
        "category": "Autonomous Agents",
        "date": "2026-10-11",
        "url": "https://openai.com/index/operator",
    },
    {
        "id": "meta-llama-3-3-70b",
        "title": "Meta Releases Llama 3.3 70B Open Foundation Model",
        "summary": "Meta released Llama 3.3 70B, matching 405B capabilities across coding and reasoning benchmarks in a size efficient for single-node hosting.",
        "tools_announced": ["Llama 3.3 70B", "Llama Stack 0.2"],
        "announced_by": "Meta AI",
        "category": "Open Source",
        "date": "2026-10-10",
        "url": "https://ai.meta.com/llama/",
    },
    {
        "id": "vllm-0-7-inference-engine",
        "title": "vLLM 0.7 Inference Engine with FP8 MLA Support",
        "summary": "The vLLM team launched version 0.7 featuring native FP8 support and optimized multi-head latent attention kernels for high-throughput serving.",
        "tools_announced": ["vLLM 0.7", "vLLM Engine"],
        "announced_by": "vLLM Project",
        "category": "Infrastructure",
        "date": "2026-10-09",
        "url": "https://github.com/vllm-project/vllm",
    },
]


def seed_database():
    print(f"Connecting to Firestore with project ID: {PROJECT_ID}...")
    db = firestore.Client(project=PROJECT_ID)
    collection_ref = db.collection(COLLECTION_NAME)

    print(f"Seeding {len(SAMPLE_ANNOUNCEMENTS)} items into '{COLLECTION_NAME}'...")
    for item in SAMPLE_ANNOUNCEMENTS:
        doc_id = item["id"]
        doc_ref = collection_ref.document(doc_id)
        doc_ref.set(item)
        print(f"  ✓ Seeded: {item['title']} ({doc_id})")

    print("\nDatabase seeding completed successfully!")


if __name__ == "__main__":
    seed_database()
