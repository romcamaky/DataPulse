"""
study_docs.py
Generates and updates per-user, per-topic study documentation after each Lab session.
Documentation is stored as structured markdown in the study_documentation table.
Claude Sonnet reads existing notes and adds only new insights — no duplicates.
"""

from datetime import datetime, timezone
import anthropic
from supabase import Client

from datapulse.config import get_anthropic_key


CLAUDE_MODEL = "claude-sonnet-4-20250514"


def _fetch_existing_doc(client: Client, user_id: str, topic_id: str) -> str | None:
    """Fetch the current markdown document for this user+topic, or None if it doesn't exist."""
    result = (
        client.table("study_documentation")
        .select("content")
        .eq("user_id", user_id)
        .eq("topic_id", topic_id)
        .maybe_single()
        .execute()
    )
    if result.data:
        return result.data["content"]
    return None


def _fetch_session_results(client: Client, user_id: str, session_id: str) -> list[dict]:
    """
    Fetch all assessment results for this study session.
    Joins with questions_bank to get the original question text.
    (Rows are scoped by session_id; assessment_results has no topic_id column.)
    """
    result = (
        client.table("assessment_results")
        .select("user_answer, is_correct, feedback, question_id, questions_bank(question_text, expected_answer)")
        .eq("user_id", user_id)
        .eq("session_id", session_id)
        .execute()
    )
    return result.data or []


def _build_prompt(
    topic_title: str,
    existing_doc: str | None,
    session_results: list[dict],
) -> str:
    """
    Build the Claude prompt.
    Instructs Claude to read existing notes and add only new insights from this session.
    """
    existing_section = existing_doc if existing_doc else "No previous notes exist for this topic yet."

    # Format session results as readable text for Claude
    results_text = ""
    for i, r in enumerate(session_results, 1):
        q = r.get("questions_bank") or {}
        correct_label = "✓ Correct" if r.get("is_correct") else "✗ Incorrect"
        results_text += f"""
Question {i}: {q.get('question_text', 'N/A')}
Expected answer: {q.get('expected_answer', 'N/A')}
Student answer: {r.get('user_answer', 'N/A')}
Result: {correct_label}
Feedback: {r.get('feedback', 'N/A')}
"""

    return f"""You are maintaining a personal study documentation file for a data engineering student.

Topic: {topic_title}

EXISTING NOTES (do not repeat these):
{existing_section}

NEW SESSION RESULTS:
{results_text}

Your task:
1. Review the existing notes carefully — do NOT repeat anything already documented.
2. Identify NEW insights from this session: new concepts understood, recurring mistakes, patterns in errors, successful problem-solving approaches.
3. Update the markdown document by APPENDING new sections only. Keep existing content exactly as-is.
4. Use this structure for any new content you add:

## Problematic Areas
- [concept]: [what went wrong and the correct explanation]

## Key Examples & Solutions
```sql or python
-- example from this session with explanation
```

## Insights & Patterns
- [observation about the student's understanding or approach]

Last updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}

Return the COMPLETE updated markdown document (existing content + new additions).
If there is nothing new to add, return the existing document unchanged.
Do not add any preamble or explanation — return only the markdown document."""


def _upsert_doc(client: Client, user_id: str, topic_id: str, content: str) -> None:
    """
    Insert or update the study_documentation row for this user+topic.
    Uses upsert on the UNIQUE (user_id, topic_id) constraint.
    """
    client.table("study_documentation").upsert(
        {
            "user_id": user_id,
            "topic_id": topic_id,
            "content": content,
            "last_updated_at": datetime.now(timezone.utc).isoformat(),
        },
        on_conflict="user_id,topic_id",
    ).execute()


def generate_study_doc_after_session(
    client: Client,
    user_id: str,
    topic_id: str,
    topic_title: str,
    session_id: str,
) -> None:
    """
    Main entry point. Called after a Lab session completes.
    Reads existing doc + session results → asks Claude to update notes → saves to Supabase.
    """
    try:
        # Fetch existing notes for this topic (may be None for first session)
        existing_doc = _fetch_existing_doc(client, user_id, topic_id)

        # Fetch all answers from this session
        session_results = _fetch_session_results(client, user_id, session_id)

        if not session_results:
            # Nothing to document if session had no answered questions
            return

        # Build prompt and call Claude Sonnet (same key resolution as Learning Lab / config)
        prompt = _build_prompt(topic_title, existing_doc, session_results)
        api_key = get_anthropic_key()
        if not api_key:
            print("[study_docs] Skipped: ANTHROPIC_API_KEY not configured.")
            return
        anthropic_client = anthropic.Anthropic(api_key=api_key)
        response = anthropic_client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        updated_content = response.content[0].text

        # Save updated document to Supabase
        _upsert_doc(client, user_id, topic_id, updated_content)

    except Exception as e:
        # Log but don't crash the app — documentation is non-critical
        print(f"[study_docs] Failed to generate study documentation: {e}")
