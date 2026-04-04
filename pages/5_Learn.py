"""
5_Learn.py
Learn mode — read theory for a topic, ask Claude follow-up questions.
Theory is pre-seeded in theory_content table (global, not per-user).
Follow-up Q&A is saved to study_documentation for the user.
"""

from __future__ import annotations

import anthropic
import streamlit as st
from supabase import Client

from datapulse.config import get_anthropic_key
from datapulse.streamlit_auth import get_authenticated_client
from datapulse.ui.styles import inject_global_styles

inject_global_styles()

CLAUDE_MODEL = "claude-sonnet-4-20250514"

# ── helpers ──────────────────────────────────────────────────────────────────


def _get_user_id_or_stop() -> str:
    user = st.session_state.get("user")
    if not user:
        st.warning("Please log in first.")
        st.stop()
    return str(user["id"])


def _load_topics(client: Client) -> list[dict]:
    """Fetch all curriculum topics ordered by topic_number."""
    result = (
        client.table("curriculum_topics")
        .select("id, topic_number, title, category, description")
        .order("topic_number")
        .execute()
    )
    return result.data or []


def _load_theory(client: Client, topic_id: str) -> str | None:
    """Fetch pre-seeded theory content for a topic. Returns markdown string or None."""
    result = (
        client.table("theory_content")
        .select("content")
        .eq("topic_id", topic_id)
        .maybe_single()
        .execute()
    )
    return result.data["content"] if result.data else None


def _load_existing_doc(client: Client, user_id: str, topic_id: str) -> str | None:
    """Fetch user's existing study documentation for this topic."""
    result = (
        client.table("study_documentation")
        .select("content")
        .eq("user_id", user_id)
        .eq("topic_id", topic_id)
        .maybe_single()
        .execute()
    )
    return result.data["content"] if result.data else None


def _ask_claude_followup(
    topic_title: str,
    theory_content: str,
    conversation_history: list[dict],
    user_question: str,
) -> str:
    """
    Send follow-up question to Claude Sonnet.
    Includes full theory content as context so Claude can answer precisely.
    Maintains conversation history for multi-turn Q&A.
    """
    api_key = get_anthropic_key()
    anthropic_client = anthropic.Anthropic(api_key=api_key)

    system_prompt = f"""You are a data engineering tutor explaining the topic: {topic_title}.

The student has just read this theory material:

{theory_content}

Answer their follow-up questions clearly and concisely.
Use PostgreSQL syntax for SQL examples.
Compare to MS SQL Server where syntax differs — the student has an MS SQL background.
Keep answers focused — 150–300 words unless a longer explanation is genuinely needed.
Use code blocks for any SQL or Python examples."""

    messages = conversation_history + [{"role": "user", "content": user_question}]

    response = anthropic_client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1024,
        system=system_prompt,
        messages=messages,
    )
    return response.content[0].text


def _save_qa_to_study_docs(
    client: Client,
    user_id: str,
    topic_id: str,
    topic_title: str,
    conversation_history: list[dict],
) -> None:
    """
    Save Q&A conversation to study_documentation.
    Calls Claude to merge new Q&A into existing notes (same as post-Lab session flow).
    Only saves if there is at least one Q&A exchange.
    """
    if not conversation_history:
        return

    # Format Q&A as readable text for the study doc generator
    qa_text = "\n\n".join(
        f"**{'Question' if m['role'] == 'user' else 'Answer'}:** {m['content']}"
        for m in conversation_history
    )

    existing_doc = _load_existing_doc(client, user_id, topic_id)

    api_key = get_anthropic_key()
    anthropic_client = anthropic.Anthropic(api_key=api_key)

    prompt = f"""You are maintaining a personal study documentation file for a data engineering student.

Topic: {topic_title}

EXISTING NOTES (do not repeat these):
{existing_doc or "No previous notes exist for this topic yet."}

NEW CONTENT — Learn mode Q&A session:
{qa_text}

Your task:
1. Review existing notes — do NOT repeat anything already documented.
2. Extract insights, clarifications, and key concepts from this Q&A.
3. Append only new content using this structure:

## Questions & Clarifications
**Q:** [question]
**A:** [key insight from the answer — summarized, not copy-pasted]

## Key Concepts Reinforced
- [concept]: [one-line explanation]

Return the COMPLETE updated markdown document (existing content + new additions).
If nothing new to add, return existing document unchanged.
Return only the markdown — no preamble."""

    response = anthropic_client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    updated_content = response.content[0].text

    client.table("study_documentation").upsert(
        {
            "user_id": user_id,
            "topic_id": topic_id,
            "content": updated_content,
        },
        on_conflict="user_id,topic_id",
    ).execute()


# ── main ─────────────────────────────────────────────────────────────────────


def main() -> None:
    st.title("📖 Learn Mode")

    client = get_authenticated_client()
    user_id = _get_user_id_or_stop()

    topics = _load_topics(client)
    if not topics:
        st.error("No topics found.")
        return

    # ── Topic selector ────────────────────────────────────────────────────────
    topic_options = {f"{t['topic_number']}. {t['title']}": t for t in topics}
    selected_label = st.selectbox("Select a topic to study:", list(topic_options.keys()))
    selected_topic = topic_options[selected_label]
    topic_id = str(selected_topic["id"])
    topic_title = selected_topic["title"]

    # Reset conversation when topic changes
    if st.session_state.get("learn_topic_id") != topic_id:
        st.session_state["learn_topic_id"] = topic_id
        st.session_state["learn_conversation"] = []

    # ── Theory content ────────────────────────────────────────────────────────
    theory = _load_theory(client, topic_id)
    if not theory:
        st.warning("Theory not yet available for this topic.")
        return

    with st.expander("📚 Theory", expanded=True):
        st.markdown(theory)

        # Download theory as markdown
        st.download_button(
            label="⬇️ Download as Markdown",
            data=theory,
            file_name=f"theory_{topic_title.lower().replace(' ', '_')}.md",
            mime="text/markdown",
        )

    # ── Follow-up Q&A ─────────────────────────────────────────────────────────
    st.subheader("💬 Ask a follow-up question")

    conversation: list[dict] = st.session_state.get("learn_conversation", [])

    # Display conversation history
    for msg in conversation:
        role_label = "🙋 You" if msg["role"] == "user" else "🤖 Claude"
        st.markdown(f"**{role_label}:** {msg['content']}")
        st.divider()

    user_question = st.text_area("Your question:", key="learn_question_input", height=100)

    col1, col2 = st.columns([1, 1])

    with col1:
        if st.button("Ask Claude", use_container_width=True):
            if not user_question.strip():
                st.warning("Please enter a question.")
            else:
                with st.spinner("Thinking..."):
                    try:
                        answer = _ask_claude_followup(
                            topic_title=topic_title,
                            theory_content=theory,
                            conversation_history=conversation,
                            user_question=user_question.strip(),
                        )
                        # Append both question and answer to conversation history
                        conversation.append({"role": "user", "content": user_question.strip()})
                        conversation.append({"role": "assistant", "content": answer})
                        st.session_state["learn_conversation"] = conversation
                        st.rerun()
                    except Exception as e:
                        st.error(f"Could not get response: {e}")

    with col2:
        if st.button("Save & Finish Session", use_container_width=True, type="primary"):
            if not conversation:
                st.info("No Q&A to save yet.")
            else:
                with st.spinner("Saving to your study notes..."):
                    try:
                        _save_qa_to_study_docs(
                            client=client,
                            user_id=user_id,
                            topic_id=topic_id,
                            topic_title=topic_title,
                            conversation_history=conversation,
                        )
                        st.session_state["learn_conversation"] = []
                        st.success("✅ Saved to your study documentation!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Could not save notes: {e}")


if __name__ == "__main__":
    main()
