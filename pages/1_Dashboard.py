"""Dashboard - Skill gaps, recommendations, curriculum progress, and market trends."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd
import streamlit as st

from supabase import Client

from datapulse.streamlit_auth import get_authenticated_client
from datapulse.ui.styles import inject_global_styles

inject_global_styles()

def _get_user_id_or_stop() -> str:
    """Resolve the current user's UUID from session state."""
    user = st.session_state.get("user") or {}
    user_id = user.get("id")
    if user_id is None:
        st.warning("User identity is missing. Please log in again.")
        st.stop()
    return str(user_id)


def _render_status_badge(status: str) -> None:
    """Render a colored status badge for curriculum topic cards."""
    # Phase 2 decision: assessed is treated as completed and shown in green.
    mapping = {
        "not_started": ("Not started", "#94A3B8"),
        "in_progress": ("In progress", "#3B82F6"),
        "assessed": ("Completed", "#22C55E"),
    }
    label, color = mapping.get(status, ("Not started", "#94A3B8"))
    st.markdown(
        (
            f'<span style="background-color:{color}; color:white; '
            f'padding:2px 10px; border-radius:999px; font-size:12px; font-weight:700;">'
            f"{label}</span>"
        ),
        unsafe_allow_html=True,
    )


def render_header(client: Client, user_id: str) -> None:
    """Render the dashboard heading and top-level summary metrics."""
    now = datetime.now(timezone.utc)
    subtitle = f"Week of {now.date().isoformat()}"

    st.title("Your Career Dashboard")
    st.caption(subtitle)

    # Keep each query isolated so one failure never breaks the whole page.
    skills_tracked = 0
    open_recs = 0
    topics_in_progress = 0
    topics_completed = 0

    try:
        result = (
            client.table("user_skills")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .execute()
        )
        skills_tracked = int(getattr(result, "count", 0) or 0)
    except Exception as e:  # noqa: BLE001
        st.error(f"Could not load header metrics: {e}")

    try:
        result = (
            client.table("recommendations")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .eq("status", "pending")
            .execute()
        )
        open_recs = int(getattr(result, "count", 0) or 0)
    except Exception as e:  # noqa: BLE001
        st.error(f"Could not load recommendations metric: {e}")

    try:
        result = (
            client.table("curriculum_progress")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .eq("status", "in_progress")
            .execute()
        )
        topics_in_progress = int(getattr(result, "count", 0) or 0)
    except Exception as e:  # noqa: BLE001
        st.error(f"Could not load in-progress topics metric: {e}")

    # Phase 2 decision: assessed rows are counted as completed.
    try:
        result = (
            client.table("curriculum_progress")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .eq("status", "assessed")
            .execute()
        )
        topics_completed = int(getattr(result, "count", 0) or 0)
    except Exception as e:  # noqa: BLE001
        st.error(f"Could not load completed topics metric: {e}")

    col_1, col_2, col_3, col_4 = st.columns(4)
    col_1.metric("Skills tracked", skills_tracked)
    col_2.metric("Open recommendations", open_recs)
    col_3.metric("Topics in progress", topics_in_progress)
    col_4.metric("Topics completed", topics_completed)


def render_skill_gap(client: Client, user_id: str) -> None:
    """Render user skills as grouped HTML progress bars by skill category."""
    st.subheader("Skill Gap Overview")

    # Load user skills and skill metadata in one join.
    try:
        user_skills_result = (
            client.table("user_skills")
            .select("level, skills!inner(display_name, name, category)")
            .eq("user_id", user_id)
            .execute()
        )
        user_skills_rows: list[dict[str, Any]] = list(user_skills_result.data or [])
    except Exception as e:  # noqa: BLE001
        st.error(f"Could not load Skill Gap Overview: {e}")
        st.info("No skills tracked yet. Complete onboarding to see your skill gaps.")
        return

    # Bail out early if the user has no skills tracked.
    if not user_skills_rows:
        st.info("No skills tracked yet. Complete onboarding to see your skill gaps.")
        return

    # Normalize rows for rendering.
    skill_rows: list[dict[str, Any]] = []
    for row in user_skills_rows:
        level = row.get("level")
        skill_meta = row.get("skills") or {}
        if level is None:
            continue
        skill_rows.append(
            {
                "skill_display_name": str(
                    skill_meta.get("display_name") or skill_meta.get("name") or "Unknown skill"
                ),
                "category_raw": str(skill_meta.get("category") or ""),
                "level": int(level or 0),
            }
        )

    if not skill_rows:
        st.info("No skills tracked yet. Complete onboarding to see your skill gaps.")
        return

    def _escape_html(value: str) -> str:
        return (
            value.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#x27;")
        )

    # Category display order and labels.
    category_order = [
        "language",
        "framework",
        "platform_tool",
        "engineering",
        "ai_ml",
        "soft_skill",
        "concept",
    ]
    category_label_map = {
        "language": "Languages",
        "framework": "Frameworks",
        "platform_tool": "Platforms & Tools",
        "engineering": "Engineering Skills",
        "ai_ml": "AI & ML",
        "soft_skill": "Soft Skills",
        "concept": "Other",
    }

    # Render progress bars per category.
    for category_raw in category_order:
        category_skills = [r for r in skill_rows if r.get("category_raw") == category_raw]
        if not category_skills:
            continue

        category_skills_sorted = sorted(
            category_skills,
            key=lambda row: int(row.get("level") or 0),
            reverse=True,
        )

        category_rows_html: list[str] = []
        for skill in category_skills_sorted:
            skill_name = _escape_html(str(skill.get("skill_display_name") or "Unknown skill"))
            level = max(0, min(5, int(skill.get("level") or 0)))
            pct = (level / 5) * 100
            category_rows_html.append(
                (
                    f"""<div style="display:flex; align-items:center; margin-bottom:10px; 
            padding:8px 12px; background:#FFFFFF; border:1px solid #E2E8F0;
            border-radius:8px;">
  <div style="width:180px; font-size:13px; font-weight:500; color:#1E293B;
              white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
              flex-shrink:0;">{skill_name}</div>
  <div style="flex:1; background:#E2E8F0; border-radius:4px; height:8px;
              margin:0 16px;">
    <div style="width:{pct}%; background:#14B8A6; border-radius:4px;
                height:8px; transition:width 0.3s ease;"></div>
  </div>
  <div style="width:32px; font-size:12px; color:#64748B;
              text-align:right; flex-shrink:0;">{level}/5</div>
</div>"""
                )
            )

        all_skill_rows_html = "".join(category_rows_html)
        html_block = f"""
<div style="background:#F0FDFA; border-radius:12px; padding:12px 16px;
            margin-bottom:16px;">
{all_skill_rows_html}
</div>
"""

        col, _ = st.columns([1, 1])
        with col:
            st.subheader(category_label_map.get(category_raw, category_raw))
            st.markdown(html_block, unsafe_allow_html=True)

    # Keep the existing "Top Skill Gaps" table below the charts.
    try:
        gap_result = (
            client.table("mart_skill_gap_analysis")
            .select("gap_rank, skill_display_name, user_level, demand_score, gap_score_normalized")
            .eq("user_id", user_id)
            .execute()
        )
        gap_rows: list[dict[str, Any]] = list(gap_result.data or [])
    except Exception as e:  # noqa: BLE001
        st.error(f"Could not load Top Skill Gaps: {e}")
        gap_rows = []

    if gap_rows:
        gap_df = pd.DataFrame(gap_rows)
        if "gap_rank" in gap_df.columns:
            gap_df = gap_df.sort_values("gap_rank").head(10)
        gap_df = gap_df.rename(
            columns={
                "gap_rank": "Rank",
                "skill_display_name": "Skill",
                "user_level": "Your level",
                "demand_score": "Market demand",
                "gap_score_normalized": "Gap score (0-10)",
            }
        )
        ordered_cols = ["Rank", "Skill", "Your level", "Market demand", "Gap score (0-10)"]
        gap_df = gap_df[[c for c in ordered_cols if c in gap_df.columns]]
    else:
        st.info("No skill gaps found yet.")
        gap_df = pd.DataFrame(
            columns=["Rank", "Skill", "Your level", "Market demand", "Gap score (0-10)"]
        )

    col, _ = st.columns([2, 1])
    with col:
        st.markdown("### Top Skill Gaps")
        st.dataframe(
            gap_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Rank": st.column_config.NumberColumn("Rank", width="small"),
                "Skill": st.column_config.TextColumn("Skill", width="large"),
                "Your level": st.column_config.NumberColumn("Your level", width="medium"),
                "Market demand": st.column_config.NumberColumn("Market demand", width="medium"),
                "Gap score (0-10)": st.column_config.NumberColumn("Gap score (0-10)", width="medium"),
            },
        )


def render_recommendations(client: Client, user_id: str) -> None:
    """Render top pending recommendations as bordered list cards."""
    st.subheader("Top Recommendations")

    # Use existing schema fields and sorting from current recommendations model.
    try:
        recs_result = (
            client.table("recommendations")
            .select("id, skill_id, priority_tier, recommendation_text, gap_rank, status, generated_at")
            .eq("user_id", user_id)
            .eq("status", "pending")
            .order("gap_rank")
            .order("generated_at", desc=True)
            .limit(5)
            .execute()
        )
        rec_rows: list[dict[str, Any]] = list(recs_result.data or [])
    except Exception as e:  # noqa: BLE001
        st.error(f"Could not load Top Recommendations: {e}")
        return

    if not rec_rows:
        st.info("No pending recommendations. The weekly pipeline will generate these automatically.")
        return

    skill_map: dict[str, str] = {}
    try:
        skill_ids = [str(row["skill_id"]) for row in rec_rows if row.get("skill_id")]
        if skill_ids:
            skills_result = (
                client.table("skills")
                .select("id, display_name, name")
                .in_("id", skill_ids)
                .execute()
            )
            for skill in list(skills_result.data or []):
                sid = skill.get("id")
                if sid is None:
                    continue
                label = skill.get("display_name") or skill.get("name") or "Unknown skill"
                skill_map[str(sid)] = str(label)
    except Exception as e:  # noqa: BLE001
        st.error(f"Could not load recommendation skill names: {e}")

    for rec in rec_rows:
        priority_tier = str(rec.get("priority_tier") or "unknown")
        rec_text = str(rec.get("recommendation_text") or "").strip()
        gap_rank = rec.get("gap_rank")
        sid = rec.get("skill_id")
        skill_name = skill_map.get(str(sid), str(sid)) if sid is not None else "Skill"
        title = f"{priority_tier.replace('_', ' ').title()}: {skill_name}"

        with st.container():
            st.markdown(
                (
                    '<div style="border:1px solid #e5e7eb; border-radius:8px; '
                    'padding:12px; margin-bottom:10px;">'
                    f"<div style='font-weight:800;'>{title}</div>"
                    f"<div style='margin-top:6px; margin-bottom:8px;'>{rec_text or '(No text provided.)'}</div>"
                    "<div style='font-size:12px; color:#111827;'>"
                    f"Priority: {priority_tier}"
                    + (f" | Gap rank: {gap_rank}" if gap_rank is not None else "")
                    + "</div></div>"
                ),
                unsafe_allow_html=True,
            )


def render_curriculum_progress(client: Client, user_id: str) -> None:
    """Render all curriculum topics in a four-column card grid with status badges."""
    st.subheader("Curriculum Progress (20 Topics)")

    try:
        topics_result = (
            client.table("curriculum_topics")
            .select("id, topic_number, title, category")
            .order("topic_number")
            .execute()
        )
        topic_rows: list[dict[str, Any]] = list(topics_result.data or [])
    except Exception as e:  # noqa: BLE001
        st.error(f"Could not load Curriculum Progress: {e}")
        return

    if not topic_rows:
        st.info("No curriculum topics found. Run the Learning Lab migration to seed topics.")
        return

    progress_map: dict[str, str] = {}
    try:
        progress_result = (
            client.table("curriculum_progress")
            .select("topic_id, status")
            .eq("user_id", user_id)
            .execute()
        )
        progress_rows: list[dict[str, Any]] = list(progress_result.data or [])
        for row in progress_rows:
            topic_id = row.get("topic_id")
            status = row.get("status") or "not_started"
            if topic_id is not None:
                progress_map[str(topic_id)] = str(status)
    except Exception as e:  # noqa: BLE001
        st.error(f"Could not load user curriculum progress: {e}")

    columns = st.columns(4)
    for idx, topic in enumerate(topic_rows):
        topic_id = topic.get("id")
        topic_number = topic.get("topic_number")
        title = str(topic.get("title") or "")
        status = progress_map.get(str(topic_id), "not_started") if topic_id is not None else "not_started"

        with columns[idx % 4]:
            st.markdown(f"**#{topic_number}**")
            st.caption(title if len(title) <= 42 else f"{title[:39]}...")
            _render_status_badge(status)


def render_market_trends(client: Client, user_id: str) -> None:
    """Render the latest three market signals as horizontal cards."""
    st.subheader("Market Trends This Week")

    # Phase 2 decision: use market_signals (signal_type, summary, extracted_at).
    try:
        signals_result = (
            client.table("market_signals")
            .select("signal_type, skill_name_raw, summary, extracted_at")
            .order("extracted_at", desc=True)
            .limit(3)
            .execute()
        )
        signal_rows: list[dict[str, Any]] = list(signals_result.data or [])
    except Exception as e:  # noqa: BLE001
        st.error(f"Could not load Market Trends This Week: {e}")
        return

    if not signal_rows:
        st.info("Market trend analysis runs every Sunday. Check back after the first pipeline run.")
        return

    cards = st.columns(3)
    for idx, signal in enumerate(signal_rows[:3]):
        with cards[idx]:
            signal_type = str(signal.get("signal_type") or "signal")
            skill_name = str(signal.get("skill_name_raw") or "")
            summary = str(signal.get("summary") or "").strip()
            extracted_at = signal.get("extracted_at")
            timestamp_text = str(extracted_at) if extracted_at else "n/a"

            st.markdown(
                (
                    f"<div style='font-weight:900; margin-bottom:4px;'>"
                    f"{signal_type.replace('_', ' ').title()}</div>"
                    f"<div style='font-size:12px; color:#6b7280; margin-bottom:8px;'>"
                    f"{skill_name if skill_name else 'Market signal'} · {timestamp_text}</div>"
                    f"<div style='white-space:pre-wrap;'>{summary or '(No summary)'}</div>"
                ),
                unsafe_allow_html=True,
            )


def main() -> None:
    """Render the full dashboard page from top to bottom."""
    # Rebuild an authenticated Supabase client from tokens so direct navigation to
    # this `pages/` module doesn't lose the client object between reruns.
    client = get_authenticated_client()
    user_id = _get_user_id_or_stop()

    render_header(client, user_id)
    render_skill_gap(client, user_id)
    render_recommendations(client, user_id)
    render_curriculum_progress(client, user_id)
    render_market_trends(client, user_id)


if __name__ == "__main__":
    main()
