"""
seed_theory.py
One-time script to generate theoretical explanations for all curriculum topics.
Run manually: python -m datapulse.seed_theory
Uses Claude Sonnet to generate structured markdown per topic.
Skips topics that already have theory content (idempotent).
"""

import os
import time
from datetime import datetime, timezone

from dotenv import load_dotenv
import anthropic
from supabase import create_client

load_dotenv(override=True)  # Must run before os.environ reads below

CLAUDE_MODEL = "claude-sonnet-4-20250514"
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_KEY"]


def _build_theory_prompt(topic_title: str, topic_description: str, category: str) -> str:
    """Build the prompt that asks Claude to generate theory for one topic."""
    return f"""You are writing a study guide for a data engineering student transitioning from data analysis.
Her background: strong SQL (MS SQL Server), Power BI, basic Python, learning PostgreSQL and dbt.

Write a complete theoretical explanation for this topic that she can read BEFORE doing practice exercises.

Topic: {topic_title}
Category: {category}
Description: {topic_description}

Structure your response as markdown with these exact sections:

## Overview
2-3 sentences explaining what this concept is and why it matters in data engineering.

## Core Concepts
Explain each key concept clearly. For SQL/dbt topics, compare to MS SQL Server where syntax differs.
Use simple language — assume she understands the concept but not the PostgreSQL-specific syntax.

## Practical Examples
Show 2-3 realistic examples with sample data (use tables like: orders, customers, employees, sessions).
Every code block must have a comment explaining what it does and why.

## Common Mistakes
List 3-5 mistakes beginners make on this topic. For each: what goes wrong, why, and the fix.

## Quick Reference
A concise cheat sheet of the most important syntax/patterns for this topic.

Return only the markdown content. No preamble, no "here is your guide" — start directly with ## Overview."""


def generate_theory_for_all_topics() -> None:
    """
    Main function: fetches all curriculum topics, generates theory for each,
    saves to theory_content table. Skips topics already covered.
    """
    # Use service role client for seeding (bypasses RLS)
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    anthropic_client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    # Fetch all curriculum topics
    topics_result = supabase.table("curriculum_topics").select("id, title, description, category").order("topic_number").execute()
    topics = topics_result.data or []
    print(f"Found {len(topics)} topics to process.")

    # Fetch topics that already have theory (for idempotency)
    existing_result = supabase.table("theory_content").select("topic_id").execute()
    existing_topic_ids = {row["topic_id"] for row in (existing_result.data or [])}
    print(f"Already have theory for {len(existing_topic_ids)} topics — skipping those.")

    for topic in topics:
        topic_id = topic["id"]
        title = topic["title"]

        if topic_id in existing_topic_ids:
            print(f"  SKIP: {title}")
            continue

        print(f"  Generating: {title} ...", end=" ", flush=True)
        try:
            prompt = _build_theory_prompt(
                topic_title=title,
                topic_description=topic.get("description") or "",
                category=topic.get("category") or "",
            )
            response = anthropic_client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
            content = response.content[0].text

            supabase.table("theory_content").insert({
                "topic_id": topic_id,
                "content": content,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "model_used": CLAUDE_MODEL,
            }).execute()

            print("OK")
            # Pause between calls to stay within API rate limits
            time.sleep(2)

        except Exception as e:
            print(f"FAILED — {e}")
            continue

    print("Done.")


if __name__ == "__main__":
    generate_theory_for_all_topics()
