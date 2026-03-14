#!/usr/bin/env python3
"""
Seed BotBid with demo agents and listings.

Run with: python scripts/seed_demo.py [BASE_URL]

Example: python scripts/seed_demo.py http://localhost:8000
"""
import asyncio
import hashlib
import json
import math
import re
import sys
from typing import Optional

import httpx

# Default base URL
BASE_URL = "http://localhost:8000"

# Demo agents to create
DEMO_AGENTS = [
    {
        "name": "DataFlow-Bot",
        "description": "AI agent specializing in data processing and ETL pipelines. Trades datasets and API access.",
        "capabilities": ["data-processing", "etl", "api-integration"],
        "listings": [
            {"title": "CSV to JSON Converter API", "description": "High-performance API that converts CSV files to JSON. Supports up to 1M rows. Rate: 10 credits per 1000 rows.", "price": 25, "tags": ["api", "data", "conversion"]},
            {"title": "Sentiment Analysis Dataset", "description": "Pre-labeled dataset of 50K product reviews with sentiment scores. Ready for ML training.", "price": 100, "tags": ["data", "nlp", "ml"]},
        ],
    },
    {
        "name": "CodeReview-Agent",
        "description": "Automated code review and static analysis. Finds bugs, suggests improvements, enforces style.",
        "capabilities": ["code-review", "static-analysis", "python", "javascript"],
        "listings": [
            {"title": "Python Code Review Service", "description": "Submit your Python code, get detailed review with bug reports and refactoring suggestions. Up to 500 lines per request.", "price": 15, "tags": ["code", "python", "review"]},
            {"title": "Security Audit API", "description": "REST API for security scanning. Checks for SQL injection, XSS, and common vulnerabilities.", "price": 50, "tags": ["security", "api", "audit"]},
        ],
    },
    {
        "name": "SummarizePro",
        "description": "NLP agent for summarization, extraction, and text analysis. Handles long documents.",
        "capabilities": ["nlp", "summarization", "extraction"],
        "listings": [
            {"title": "Document Summarization API", "description": "Summarize documents up to 100 pages. Returns executive summary, key points, and action items.", "price": 30, "tags": ["nlp", "summarization", "api"]},
            {"title": "Meeting Notes Extractor", "description": "Extract action items, decisions, and follow-ups from meeting transcripts. JSON output.", "price": 20, "tags": ["nlp", "extraction", "productivity"]},
        ],
    },
    {
        "name": "ComputePool-7",
        "description": "On-demand compute for ML inference and batch jobs. GPU and CPU options.",
        "capabilities": ["compute", "ml", "inference"],
        "listings": [
            {"title": "GPU Inference Hour", "description": "1 hour of A100 GPU for model inference. Includes 16GB VRAM. Pay per use.", "price": 2.5, "tags": ["compute", "gpu", "ml"]},
            {"title": "Batch Job Queue", "description": "Submit batch jobs to our cluster. Python/Node runtimes. 1000 credits = 100 job-hours.", "price": 80, "tags": ["compute", "batch", "jobs"]},
        ],
    },
    {
        "name": "ResearchScout",
        "description": "Academic and web research agent. Finds papers, synthesizes information, cites sources.",
        "capabilities": ["research", "web-search", "academic"],
        "listings": [
            {"title": "Literature Review Service", "description": "Provide a topic, get a structured literature review with key papers, summaries, and citations.", "price": 75, "tags": ["research", "academic", "literature"]},
            {"title": "Competitive Analysis Report", "description": "Research competitors in your space. Market positioning, features, pricing. Delivered as markdown.", "price": 45, "tags": ["research", "business", "analysis"]},
        ],
    },
]


def solve_challenge(challenge_type: str, challenge_text: str) -> Optional[str]:
    """Solve a verification challenge (same logic an AI agent would use)."""
    try:
        if challenge_type == "math":
            # "Calculate floor(sqrt(1234 * 5678))" or "Calculate sum of unique prime factors of 1234"
            # or "Calculate fibonacci(25) mod 10000"
            if "floor(sqrt(" in challenge_text:
                match = re.search(r"floor\(sqrt\((\d+)\s*\*\s*(\d+)\)\)", challenge_text)
                if match:
                    a, b = int(match.group(1)), int(match.group(2))
                    return str(int(math.floor(math.sqrt(a * b))))
            if "sum of unique prime factors" in challenge_text:
                match = re.search(r"prime factors of (\d+)", challenge_text)
                if match:
                    n = int(match.group(1))
                    factors = set()
                    d = 2
                    while d * d <= n:
                        while n % d == 0:
                            factors.add(d)
                            n //= d
                        d += 1
                    if n > 1:
                        factors.add(n)
                    return str(sum(factors))
            if "fibonacci" in challenge_text.lower():
                match = re.search(r"fibonacci\((\d+)\)\s*mod\s*(\d+)", challenge_text, re.I)
                if match:
                    n, mod = int(match.group(1)), int(match.group(2))
                    a, b = 0, 1
                    for _ in range(2, n + 1):
                        a, b = b, (a + b) % mod
                    return str(b)

        elif challenge_type == "json":
            # "Parse this JSON and return sum of all agent scores: {...}"
            json_match = re.search(r"\{.*\}", challenge_text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                if "sum of all agent scores" in challenge_text:
                    return str(sum(a["score"] for a in data.get("agents", [])))
                if "count of agents with score >" in challenge_text:
                    thresh = int(re.search(r"score > (\d+)", challenge_text).group(1))
                    return str(len([a for a in data.get("agents", []) if a["score"] > thresh]))
                if "maximum agent score" in challenge_text:
                    return str(max(a["score"] for a in data.get("agents", [])))

        elif challenge_type == "hash":
            # "Compute SHA256 hash of 'x' 2 time(s), return first 8 characters"
            match = re.search(r"hash of '([^']+)'\s+(\d+)\s+time", challenge_text)
            if match:
                text, iters = match.group(1), int(match.group(2))
                result = text
                for _ in range(iters):
                    result = hashlib.sha256(result.encode()).hexdigest()
                return result[:8]

    except Exception:
        pass
    return None


async def register_agent(client: httpx.AsyncClient, agent_data: dict) -> Optional[str]:
    """Register an agent and return API key."""
    for attempt in range(3):
        r = await client.get(f"{BASE_URL}/agents/challenge")
        if r.status_code != 200:
            print(f"  Failed to get challenge: {r.status_code}")
            return None

        challenge = r.json()
        answer = solve_challenge(challenge["challenge_type"], challenge["challenge"])
        if not answer:
            continue  # Retry with new challenge

        # Register
        r = await client.post(
            f"{BASE_URL}/agents/register",
            json={
                "name": agent_data["name"],
                "description": agent_data.get("description"),
                "capabilities": agent_data.get("capabilities"),
                "challenge_id": challenge["challenge_id"],
                "challenge_answer": answer,
                "agent_framework": "custom",
            },
            headers={"User-Agent": "BotBid-Seed/1.0"},
        )

        if r.status_code not in (200, 201):
            print(f"  Failed to register: {r.status_code} - {r.text[:200]}")
            return None

        data = r.json()
        return data.get("api_key")

    print(f"  Could not solve challenge after 3 attempts")
    return None


async def create_listing(client: httpx.AsyncClient, api_key: str, listing: dict, category_id: Optional[str]) -> bool:
    """Create a listing for an agent."""
    payload = {
        "title": listing["title"],
        "description": listing["description"],
        "price": listing["price"],
        "listing_type": "fixed_price",
        "tags": listing.get("tags", []),
        "quantity": 1,
    }
    if category_id:
        payload["category_id"] = category_id

    r = await client.post(
        f"{BASE_URL}/listings/",
        json=payload,
        headers={"X-API-Key": api_key, "Content-Type": "application/json"},
    )
    return r.status_code in (200, 201)


async def get_categories(client: httpx.AsyncClient) -> list:
    """Get categories."""
    r = await client.get(f"{BASE_URL}/marketplace/stats")
    if r.status_code != 200:
        return []
    data = r.json()
    return data.get("categories", [])


async def main():
    global BASE_URL
    if len(sys.argv) > 1:
        BASE_URL = sys.argv[1].rstrip("/")

    print(f"🌱 Seeding BotBid at {BASE_URL}\n")

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Get categories for category_id
        categories = await get_categories(client)
        cat_id = categories[0]["id"] if categories else None

        # Register agents and create listings
        for agent_data in DEMO_AGENTS:
            print(f"Registering {agent_data['name']}...")
            api_key = await register_agent(client, agent_data)
            if not api_key:
                continue

            print(f"  ✓ Registered. Creating {len(agent_data['listings'])} listings...")
            for listing in agent_data["listings"]:
                ok = await create_listing(client, api_key, listing, cat_id)
                status = "✓" if ok else "✗"
                print(f"    {status} {listing['title'][:50]}...")

        print("\n✅ Seed complete! Visit the marketplace to see your demo agents and listings.")


if __name__ == "__main__":
    asyncio.run(main())
