"""Learning Lab page with Practice and Assess modes."""

from __future__ import annotations

import json
import random
import threading
from datetime import datetime, timezone
from typing import Any

import requests
import streamlit as st
from supabase import Client
from uuid import uuid4

from datapulse.config import get_anthropic_key
from datapulse.streamlit_auth import get_authenticated_client

CLAUDE_MODEL = "claude-sonnet-4-20250514"
CLAUDE_SYSTEM_PROMPT = (
    "You are a data engineering tutor reviewing a student's answer. "
    "Be direct and constructive. Identify what is correct, what is wrong, "
    "and explain the fix. Keep response under 200 words."
)


def _get_user_id_or_stop() -> str:
    """Return current user id from session state."""
    user = st.session_state.get("user") or {}
    user_id = user.get("id")
    if not user_id:
        st.warning("Please log in first.")
        st.stop()
    return str(user_id)


def _question_badge_style(question_type: str) -> tuple[str, str]:
    """Return label and color for question type badge."""
    mapping = {
        "write_query": ("Write Query", "#2563EB"),
        "predict_output": ("Predict Output", "#16A34A"),
        "find_bug": ("Find Bug", "#DC2626"),
        "conceptual": ("Conceptual", "#6B7280"),
    }
    return mapping.get(question_type, ("Question", "#475569"))


def _difficulty_stars(difficulty: int | None) -> str:
    """Render difficulty as stars."""
    if difficulty == 1:
        return "★☆☆"
    if difficulty == 2:
        return "★★☆"
    return "★★★"


def _reset_practice_state() -> None:
    """Reset practice-mode specific session state keys."""
    st.session_state["lab_question"] = None
    st.session_state["lab_show_answer"] = False
    st.session_state["lab_user_answer"] = ""
    st.session_state["lab_feedback"] = None


def _reset_assess_state() -> None:
    """Reset assessment-mode specific session state keys."""
    st.session_state["assess_questions"] = None
    st.session_state["assess_index"] = 0
    st.session_state["assess_answers"] = []
    st.session_state["assess_results"] = []
    st.session_state["assess_complete"] = False
    st.session_state["assess_current_answer"] = ""
    st.session_state["assess_progress_saved"] = False


def render_topic_selector(client: Client) -> tuple[str | None, str | None]:
    """Render topic and mode selectors, returning (topic_id, mode)."""
    st.title("Learning Lab")

    # Load all curriculum topics.
    try:
        topics_result = (
            client.table("curriculum_topics")
            .select("id, topic_number, title")
            .gte("topic_number", 1)
            .order("topic_number")
            .execute()
        )
        topics = list(topics_result.data or [])
    except Exception as e:  # noqa: BLE001
        st.error(f"Could not load topics: {e}")
        return None, None

    if not topics:
        st.info("No topics available yet. Run the Learning Lab migrations and seed questions first.")
        return None, None

    topic_labels = [f"Topic {t['topic_number']}: {t['title']}" for t in topics]
    topic_map = {label: t for label, t in zip(topic_labels, topics)}

    # Keep current topic if already selected.
    default_label = topic_labels[0]
    selected_topic_id = st.session_state.get("lab_topic_id")
    if selected_topic_id:
        for label, topic in topic_map.items():
            if topic.get("id") == selected_topic_id:
                default_label = label
                break

    selected_label = st.selectbox(
        "Choose a topic",
        options=topic_labels,
        index=topic_labels.index(default_label),
    )
    selected_topic = topic_map[selected_label]
    topic_id = str(selected_topic["id"])

    # Detect topic changes and reset mode-specific state.
    if st.session_state.get("lab_topic_id") != topic_id:
        st.session_state["lab_topic_id"] = topic_id
        _reset_practice_state()
        _reset_assess_state()

    # Mode buttons.
    mode_col_1, mode_col_2 = st.columns(2)
    with mode_col_1:
        if st.button("Practice Mode", use_container_width=True):
            st.session_state["lab_mode"] = "practice"
            _reset_practice_state()
            _reset_assess_state()
    with mode_col_2:
        if st.button("Assess Mode", use_container_width=True):
            st.session_state["lab_mode"] = "assess"
            _reset_practice_state()
            _reset_assess_state()

    return topic_id, st.session_state.get("lab_mode")


def generate_questions(
    client: Client,
    topic_id: str,
    topic_title: str,
    count: int = 5,
) -> None:
    """Generate and insert new practice questions for a topic using Claude Haiku."""
    # Resolve API key first so this function can fail fast and non-fatally.
    api_key = get_anthropic_key()
    if not api_key:
        st.warning("Question generation skipped: missing ANTHROPIC_API_KEY.")
        return

    # Build generation prompt with strict JSON-only output requirements.
    system_prompt = (
        "You are a data engineering tutor. "
        f"Generate exactly {count} practice questions for the topic: {topic_title}.\n\n"
        "Return ONLY a JSON array with no markdown, no preamble. Each object:\n"
        "{\n"
        "  'question_type': one of write_query/predict_output/find_bug/conceptual,\n"
        "  'difficulty': integer 1-3,\n"
        "  'question_text': string,\n"
        "  'sample_data': string or null (SQL CREATE+INSERT for write_query/predict_output),\n"
        "  'expected_answer': string,\n"
        "  'hints': string\n"
        "}\n\n"
        "Use realistic business scenarios (employees, orders, sales). "
        "All SQL must be valid PostgreSQL. "
        "Mix difficulty levels and question types."
    )

    try:
        # Call Claude Haiku using the same API pattern as feedback calls.
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 2000,
                "system": system_prompt,
                "messages": [{"role": "user", "content": f"Topic: {topic_title}"}],
            },
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        content = payload.get("content") or []
        if not content:
            st.warning("Question generation failed: Claude returned empty content.")
            return

        # Parse JSON array returned by Claude, with light fence cleanup fallback.
        raw_text = str(content[0].get("text") or "").strip()
        cleaned_text = raw_text.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(cleaned_text)
        if not isinstance(parsed, list):
            st.warning("Question generation failed: response was not a JSON array.")
            return

        # Build rows for deduplicated insert/upsert into questions_bank.
        insert_rows: list[dict[str, Any]] = []
        for item in parsed:
            if not isinstance(item, dict):
                continue
            question_type = str(item.get("question_type") or "").strip()
            difficulty_raw = item.get("difficulty")
            question_text = str(item.get("question_text") or "").strip()
            expected_answer = str(item.get("expected_answer") or "").strip()
            hints = str(item.get("hints") or "").strip()
            sample_data = item.get("sample_data")

            # Skip malformed entries to keep generation non-fatal.
            if not question_type or not question_text or not expected_answer:
                continue

            try:
                difficulty = int(difficulty_raw)
            except (TypeError, ValueError):
                difficulty = 2
            difficulty = max(1, min(3, difficulty))

            insert_rows.append(
                {
                    "topic_id": topic_id,
                    "question_type": question_type,
                    "difficulty": difficulty,
                    "question_text": question_text,
                    "sample_data": sample_data if sample_data is not None else None,
                    "expected_answer": expected_answer,
                    "hints": hints,
                }
            )

        if not insert_rows:
            st.warning("Question generation failed: no valid question rows parsed.")
            return

        # Upsert with conflict target to avoid duplicates when regenerating.
        client.table("questions_bank").upsert(
            insert_rows,
            on_conflict="topic_id,question_type,difficulty,question_text",
            ignore_duplicates=True,
        ).execute()

    except json.JSONDecodeError as e:
        st.warning(f"Question generation failed: invalid JSON from Claude ({e}).")
    except Exception as e:  # noqa: BLE001
        st.warning(f"Question generation failed: {e}")


def _topic_title_or_fallback(client: Client, topic_id: str) -> str:
    """Return topic title for generation prompts, with safe fallback text."""
    try:
        result = (
            client.table("curriculum_topics")
            .select("title")
            .eq("id", topic_id)
            .limit(1)
            .execute()
        )
        rows = list(result.data or [])
        if rows and rows[0].get("title"):
            return str(rows[0]["title"])
    except Exception:
        pass
    return f"Topic {topic_id}"


def smart_load_question(
    client: Client,
    topic_id: str,
    user_id: str,
) -> dict[str, Any] | None:
    """Load one question with priority: unseen -> previously incorrect -> any."""
    # Load all questions for the topic.
    try:
        questions_result = (
            client.table("questions_bank")
            .select(
                "id, topic_id, difficulty, question_type, question_text, "
                "sample_data, expected_answer, hints, created_at"
            )
            .eq("topic_id", topic_id)
            .execute()
        )
        all_questions = list(questions_result.data or [])
    except Exception as e:  # noqa: BLE001
        st.error(f"Could not load questions: {e}")
        return None

    if not all_questions:
        return None

    # Load all answered question ids for this user.
    try:
        seen_result = (
            client.table("assessment_results")
            .select("question_id")
            .eq("user_id", user_id)
            .execute()
        )
        seen_rows = list(seen_result.data or [])
    except Exception:
        seen_rows = []
    seen_ids = {str(row.get("question_id")) for row in seen_rows if row.get("question_id")}

    # Load question ids the user answered incorrectly.
    try:
        incorrect_result = (
            client.table("assessment_results")
            .select("question_id")
            .eq("user_id", user_id)
            .eq("is_correct", False)
            .execute()
        )
        incorrect_rows = list(incorrect_result.data or [])
    except Exception:
        incorrect_rows = []
    incorrect_ids = {
        str(row.get("question_id")) for row in incorrect_rows if row.get("question_id")
    }

    # Build priority pools.
    pool_a = [q for q in all_questions if str(q.get("id")) not in seen_ids]
    pool_b = [q for q in all_questions if str(q.get("id")) in incorrect_ids]
    pool_c = all_questions

    # Trigger non-blocking generation when unseen pool is running low.
    if len(pool_a) < 3:
        topic_title = _topic_title_or_fallback(client, topic_id)
        threading.Thread(
            target=generate_questions,
            args=(client, topic_id, topic_title, 5),
            daemon=True,
        ).start()

    # Priority selection: unseen -> incorrect -> full rotation.
    if pool_a:
        return random.choice(pool_a)
    if pool_b:
        return random.choice(pool_b)
    return random.choice(pool_c) if pool_c else None


def render_question_display(question: dict[str, Any]) -> None:
    """Render question metadata, text, and optional sample data."""
    question_type = str(question.get("question_type") or "")
    difficulty = int(question.get("difficulty") or 1)
    question_text = str(question.get("question_text") or "")
    sample_data = question.get("sample_data")

    label, color = _question_badge_style(question_type)
    stars = _difficulty_stars(difficulty)

    badge_col, stars_col = st.columns([1, 3])
    with badge_col:
        st.markdown(
            (
                f"<span style='background-color:{color}; color:white; "
                "padding:2px 10px; border-radius:999px; font-size:12px; font-weight:700;'>"
                f"{label}</span>"
            ),
            unsafe_allow_html=True,
        )
    with stars_col:
        st.write(f"Difficulty: {stars}")

    st.markdown(f"### {question_text}")

    if sample_data:
        st.code(str(sample_data), language="sql")


def call_claude_feedback(
    question_text: str,
    expected_answer: str,
    user_answer: str,
) -> tuple[str, bool]:
    """Call Claude API and return feedback text with strict correctness detection."""
    api_key = get_anthropic_key()
    if not api_key:
        raise RuntimeError("Missing ANTHROPIC_API_KEY in environment or Streamlit secrets.")

    user_message = (
        f"Question: {question_text}\n"
        f"Expected answer: {expected_answer}\n"
        f"Student answer: {user_answer}\n"
        "Give feedback."
    )

    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": CLAUDE_MODEL,
            "max_tokens": 300,
            "system": CLAUDE_SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": user_message}],
        },
        timeout=45,
    )
    response.raise_for_status()
    payload = response.json()
    content = payload.get("content") or []
    if not content:
        raise RuntimeError("Claude returned an empty response.")

    feedback_text = str(content[0].get("text") or "").strip()
    feedback_lower = feedback_text.lower()
    is_correct = (
        "correct" in feedback_lower
        and "incorrect" not in feedback_lower
        and "not correct" not in feedback_lower
        and "incomplete" not in feedback_lower
        and "wrong" not in feedback_lower
    )
    return feedback_text, is_correct


def save_assessment_result(
    client: Client,
    user_id: str,
    topic_id: str,
    question_id: str,
    user_answer: str,
    feedback: str,
    is_correct: bool,
) -> None:
    """Persist one assessed answer row using the actual schema (session_id)."""
    # Create one study_session row first, then attach the assessment_results row to it.
    # Per the requested flow, we mark this session as "practice".
    session_id = str(uuid4())
    started_at_iso = datetime.now(timezone.utc).isoformat()

    client.table("study_sessions").insert(
        {
            "id": session_id,
            "user_id": user_id,
            "topic_id": topic_id,
            "mode": "practice",
            "started_at": started_at_iso,
        }
    ).execute()

    client.table("assessment_results").insert(
        {
            "id": str(uuid4()),
            "user_id": user_id,
            "session_id": session_id,
            "question_id": question_id,
            "user_answer": user_answer,
            "is_correct": is_correct,
            "feedback": feedback,
        }
    ).execute()


def _upsert_curriculum_progress(
    client: Client,
    user_id: str,
    topic_id: str,
    best_score: int,
) -> None:
    """Upsert curriculum progress using the actual schema columns.

    best_score is an integer in 0..5. Attempts is incremented by 1 on each
    retake and best_score is kept as the maximum across attempts.
    """
    now_iso = datetime.now(timezone.utc).isoformat()

    # Read current attempts/best_score so we can increment attempts and keep the best score.
    existing = (
        client.table("curriculum_progress")
        .select("attempts, best_score")
        .eq("user_id", user_id)
        .eq("topic_id", topic_id)
        .limit(1)
        .execute()
    )
    rows = list(existing.data or [])
    prev_attempts = int(rows[0].get("attempts") or 0) if rows else 0
    prev_best = int(rows[0].get("best_score") or 0) if rows else 0

    new_best_score = max(prev_best, int(best_score))
    new_attempts = prev_attempts + 1

    # Upsert with the computed values; keeps the best score across retakes.
    client.table("curriculum_progress").upsert(
        {
            "user_id": user_id,
            "topic_id": topic_id,
            "status": "assessed",
            "best_score": new_best_score,
            "attempts": new_attempts,
            "last_studied_at": now_iso,
        },
        on_conflict="user_id,topic_id",
    ).execute()


def sync_skills_after_assessment(
    client: Client,
    user_id: str,
    topic_id: str,
    best_score: int,
) -> None:
    """Sync `user_skills` for skills mapped to an assessed topic.

    This is non-fatal: any sync failure is caught and surfaced via
    `st.warning()` without blocking assessment completion.
    """
    # Guard against sync when the assessment score is not high enough.
    try:
        best_score_int = int(best_score)
    except (TypeError, ValueError) as e:
        st.warning(f"Skill sync skipped: invalid best_score `{best_score}` ({e}).")
        return

    # Only sync after "pass-ish" outcomes to avoid downgrading from failures.
    if best_score_int < 3:
        return

    now_iso = datetime.now(timezone.utc).isoformat()

    try:
        # Load all skills mapped to this curriculum topic.
        mapping_result = (
            client.table("topic_skill_mapping")
            .select("skill_id")
            .eq("topic_id", topic_id)
            .execute()
        )
        mapping_rows = list(mapping_result.data or [])
        skill_ids = [str(r.get("skill_id")) for r in mapping_rows if r.get("skill_id")]

        # Nothing to do if no skills are mapped for this topic.
        if not skill_ids:
            return

        # Iterate over mapped skills and upsert the user's level.
        for skill_id in skill_ids:
            try:
                existing_result = (
                    client.table("user_skills")
                    .select("level")
                    .eq("user_id", user_id)
                    .eq("skill_id", skill_id)
                    .limit(1)
                    .execute()
                )
                existing_rows = list(existing_result.data or [])

                # If a skill row already exists, only increase level gradually.
                if existing_rows:
                    current_level_raw = existing_rows[0].get("level")
                    current_level = int(current_level_raw or 1)
                    new_level = min(best_score_int, current_level + 1)

                    # Only write when this assessment produces an upgrade.
                    if new_level > current_level:
                        client.table("user_skills").update({"level": new_level}).eq(
                            "user_id", user_id
                        ).eq("skill_id", skill_id).execute()
                    continue

                # Otherwise insert a new row with initial level and evidence.
                # Note: the user spec asks for evidence_type='assessment', but
                # the DB schema constrains evidence_type to a fixed enum that
                # does not include 'assessment'. We use 'self_assessment'.
                insert_level = min(best_score_int, 1)
                client.table("user_skills").insert(
                    {
                        "user_id": user_id,
                        "skill_id": skill_id,
                        "level": insert_level,
                        "confidence": "medium",
                        "evidence_type": "self_assessment",
                        "evidence_detail": f"Completed learning lab assessment for topic {topic_id}",
                        "visibility": "public",
                        "last_assessed_at": now_iso,
                    }
                ).execute()

            except Exception as e:  # noqa: BLE001
                st.warning(f"Skill sync failed for skill `{skill_id}`: {e}")
                continue

    except Exception as e:  # noqa: BLE001
        st.warning(f"Skill sync failed for topic `{topic_id}`: {e}")


def _load_assessment_question_set(client: Client, topic_id: str) -> list[dict[str, Any]]:
    """Load 5 assessment questions with target difficulty distribution."""
    try:
        result = (
            client.table("questions_bank")
            .select(
                "id, topic_id, difficulty, question_type, question_text, "
                "sample_data, expected_answer, hints, created_at"
            )
            .eq("topic_id", topic_id)
            .execute()
        )
        all_rows = list(result.data or [])
    except Exception as e:  # noqa: BLE001
        st.error(f"Could not load assessment questions: {e}")
        return []

    if not all_rows:
        return []

    by_diff = {1: [], 2: [], 3: []}
    for row in all_rows:
        diff = int(row.get("difficulty") or 1)
        if diff in by_diff:
            by_diff[diff].append(row)

    # Target: 1 easy, 2 medium, 2 hard.
    selected: list[dict[str, Any]] = []
    selected.extend(random.sample(by_diff[1], min(1, len(by_diff[1]))))
    selected.extend(random.sample(by_diff[2], min(2, len(by_diff[2]))))
    selected.extend(random.sample(by_diff[3], min(2, len(by_diff[3]))))

    # Fill remaining slots from any unused questions.
    selected_ids = {str(q["id"]) for q in selected}
    remaining = [q for q in all_rows if str(q["id"]) not in selected_ids]
    need = 5 - len(selected)
    if need > 0 and remaining:
        selected.extend(random.sample(remaining, min(need, len(remaining))))

    # Ensure exactly up to 5 unique questions.
    unique = {}
    for q in selected:
        unique[str(q["id"])] = q
    selected = list(unique.values())[:5]
    random.shuffle(selected)
    return selected


def render_practice_mode(client: Client, user_id: str, topic_id: str) -> None:
    """Render practice-mode workflow."""
    st.subheader("Practice Mode")

    # Load a prioritized question initially or when topic changed.
    if not st.session_state.get("lab_question"):
        st.session_state["lab_question"] = smart_load_question(client, topic_id, user_id)
        st.session_state["lab_user_answer"] = ""
        st.session_state["lab_feedback"] = None
        st.session_state["lab_show_answer"] = False

    question = st.session_state.get("lab_question")
    if not question:
        # If no question exists yet, try generating a starter set for this topic.
        topic_title = _topic_title_or_fallback(client, topic_id)
        with st.spinner("Generating questions for this topic..."):
            generate_questions(client, topic_id, topic_title, count=5)
            question = smart_load_question(client, topic_id, user_id)
            st.session_state["lab_question"] = question

        # If generation still yields no questions, show a clear error.
        if not question:
            st.error("Could not generate questions. Try again.")
            return

    render_question_display(question)

    # Collect student's free-form answer.
    st.text_area("Your answer", height=150, key="lab_user_answer")

    hint_col, check_col, next_col = st.columns(3)

    # Hint button reveals the pre-authored hint.
    with hint_col:
        if st.button("Hint", use_container_width=True):
            hint_text = question.get("hints")
            if hint_text:
                st.info(str(hint_text))
            else:
                st.info("No hint available for this question.")

    # Claude review call for current answer.
    with check_col:
        if st.button("Check with Claude", use_container_width=True):
            user_answer = str(st.session_state.get("lab_user_answer") or "").strip()
            if not user_answer:
                st.warning("Please enter your answer first.")
            else:
                try:
                    feedback, is_correct = call_claude_feedback(
                        question_text=str(question.get("question_text") or ""),
                        expected_answer=str(question.get("expected_answer") or ""),
                        user_answer=user_answer,
                    )
                    st.session_state["lab_feedback"] = feedback

                    save_assessment_result(
                        client=client,
                        user_id=user_id,
                        topic_id=topic_id,
                        question_id=str(question.get("id")),
                        user_answer=user_answer,
                        feedback=feedback,
                        is_correct=is_correct,
                    )
                except Exception as e:  # noqa: BLE001
                    st.error(f"Could not get Claude feedback: {e}")

    # Next question replaces current prompt and clears answer/feedback.
    with next_col:
        if st.button("Next question", use_container_width=True):
            st.session_state["lab_question"] = smart_load_question(client, topic_id, user_id)
            st.session_state["lab_user_answer"] = ""
            st.session_state["lab_feedback"] = None
            st.rerun()

    # Render latest feedback with requested color heuristics.
    feedback_text = st.session_state.get("lab_feedback")
    if feedback_text:
        lowered = str(feedback_text).lower()
        if "correct" in lowered and "wrong" not in lowered:
            st.success(str(feedback_text))
        elif "wrong" in lowered:
            st.error(str(feedback_text))
        else:
            st.warning(str(feedback_text))


def render_assess_mode(client: Client, user_id: str, topic_id: str) -> None:
    """Render assess-mode workflow with 5-question scoring."""
    st.subheader("Assess Mode")

    # Initialize an assessment session if needed.
    if not st.session_state.get("assess_questions"):
        questions = _load_assessment_question_set(client, topic_id)
        if not questions:
            st.info(
                "Questions for this topic are not available yet. "
                "Select a topic from 1-5 to start learning."
            )
            st.stop()
        st.session_state["assess_questions"] = questions
        st.session_state["assess_index"] = 0
        st.session_state["assess_answers"] = []
        st.session_state["assess_results"] = []
        st.session_state["assess_complete"] = False
        st.session_state["assess_current_answer"] = ""
        st.session_state["assess_progress_saved"] = False

    if st.session_state.get("assess_complete"):
        results = list(st.session_state.get("assess_results") or [])
        correct_count = sum(1 for row in results if bool(row.get("is_correct")))
        score = f"{correct_count}/5"

        st.markdown(f"### Assessment Complete - Score: {score}")

        if correct_count >= 4:
            st.success("Ready to move on")
        elif correct_count == 3:
            st.warning("Almost there - review weak areas")
        else:
            st.error("Needs more practice")

        for idx, row in enumerate(results, start=1):
            qtype = str(row.get("question_type") or "question")
            feedback = str(row.get("feedback") or "")
            icon = "✓" if bool(row.get("is_correct")) else "✗"
            st.markdown(f"**Q{idx} ({qtype})** {icon}")
            st.write(feedback)
            if idx < len(results):
                st.divider()

        # Persist summary progress once.
        if not st.session_state.get("assess_progress_saved"):
            _upsert_curriculum_progress(
                client=client,
                user_id=user_id,
                topic_id=topic_id,
                best_score=correct_count,
            )

            # Sync mapped user skill levels after curriculum progress is stored.
            sync_skills_after_assessment(
                client=client,
                user_id=user_id,
                topic_id=topic_id,
                best_score=correct_count,
            )
            st.session_state["assess_progress_saved"] = True

        action_col_1, action_col_2 = st.columns(2)
        with action_col_1:
            if st.button("Retake Assessment", use_container_width=True):
                _reset_assess_state()
                st.rerun()
        with action_col_2:
            if st.button("Back to topics", use_container_width=True):
                _reset_assess_state()
                st.session_state["lab_mode"] = None
                st.rerun()
        return

    questions = list(st.session_state.get("assess_questions") or [])
    index = int(st.session_state.get("assess_index") or 0)
    total = len(questions)
    if total == 0:
        st.info("No questions available.")
        return
    if index >= total:
        st.session_state["assess_complete"] = True
        st.rerun()
        return

    current_question = questions[index]
    st.write(f"Question {index + 1} of {total}")
    st.progress((index + 1) / total)
    render_question_display(current_question)

    answer_key = f"assess_answer_{index}"
    user_answer = st.text_area("Your answer", height=150, key=answer_key)

    if st.button("Submit Answer", use_container_width=True):
        normalized_answer = str(user_answer or "").strip()
        if not normalized_answer:
            st.warning("Please enter your answer before submitting.")
            return

        try:
            feedback, _ = call_claude_feedback(
                question_text=str(current_question.get("question_text") or ""),
                expected_answer=str(current_question.get("expected_answer") or ""),
                user_answer=normalized_answer,
            )
        except Exception as e:  # noqa: BLE001
            st.error(f"Could not get Claude feedback: {e}")
            return

        feedback_lower = feedback.lower()
        is_correct = (
            "correct" in feedback_lower
            and "incorrect" not in feedback_lower
            and "not correct" not in feedback_lower
            and "incomplete" not in feedback_lower
            and "wrong" not in feedback_lower
        )

        # Save per-question row for analytics and history.
        save_assessment_result(
            client=client,
            user_id=user_id,
            topic_id=topic_id,
            question_id=str(current_question.get("id")),
            user_answer=normalized_answer,
            feedback=feedback,
            is_correct=is_correct,
        )

        # Store in session for final report rendering.
        answers = list(st.session_state.get("assess_answers") or [])
        answers.append(normalized_answer)
        st.session_state["assess_answers"] = answers

        results = list(st.session_state.get("assess_results") or [])
        results.append(
            {
                "question_id": str(current_question.get("id")),
                "question_type": str(current_question.get("question_type") or ""),
                "is_correct": is_correct,
                "feedback": feedback,
            }
        )
        st.session_state["assess_results"] = results
        st.session_state["assess_index"] = index + 1

        if st.session_state["assess_index"] >= total:
            st.session_state["assess_complete"] = True

        st.rerun()


def main() -> None:
    """Render Learning Lab page."""
    client = get_authenticated_client()
    user_id = _get_user_id_or_stop()
    topic_id, mode = render_topic_selector(client)

    if not topic_id:
        return
    if not mode:
        st.info("Choose a mode to start learning.")
        return

    if mode == "practice":
        render_practice_mode(client, user_id, topic_id)
    elif mode == "assess":
        render_assess_mode(client, user_id, topic_id)
    else:
        st.info("Choose a valid mode to continue.")


if __name__ == "__main__":
    main()
