"""Dashboard - Skill gaps, recommendations, curriculum progress, and market trends."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd
import plotly.express as px
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
    """Render skill gaps as grouped horizontal bar charts by skill category."""
    st.subheader("Skill Gap Overview")

    # Load user's tracked skill levels.
    try:
        user_skills_result = (
            client.table("user_skills")
            .select("skill_id, level")
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

    # Load skill metadata (display name + category) so we can group charts by category.
    try:
        skill_ids = [str(row["skill_id"]) for row in user_skills_rows if row.get("skill_id")]
        if not skill_ids:
            st.info("No skills tracked yet. Complete onboarding to see your skill gaps.")
            return

        skills_result = (
            client.table("skills")
            .select("id, display_name, name, category")
            .in_("id", skill_ids)
            .execute()
        )
        skills_rows: list[dict[str, Any]] = list(skills_result.data or [])
    except Exception as e:  # noqa: BLE001
        st.error(f"Could not load skill labels: {e}")
        return

    # Build an O(1) lookup for skill id -> (display name, category).
    skill_meta_by_id: dict[str, dict[str, str]] = {}
    for skill in skills_rows:
        sid = skill.get("id")
        if sid is None:
            continue
        label = skill.get("display_name") or skill.get("name") or "Unknown skill"
        category_raw = str(skill.get("category") or "")
        skill_meta_by_id[str(sid)] = {"label": str(label), "category_raw": category_raw}

    # Reuse a single list of skill rows for chart generation.
    chart_rows: list[dict[str, Any]] = []
    for row in user_skills_rows:
        sid = row.get("skill_id")
        level = row.get("level")
        if sid is None or level is None:
            continue
        meta = skill_meta_by_id.get(str(sid)) or {"label": str(sid), "category_raw": ""}
        chart_rows.append(
            {
                "skill_display_name": str(meta["label"]),
                "category_raw": str(meta["category_raw"]),
                "level": int(level),
            }
        )

    # Stop if we could not build any skill rows.
    if not chart_rows:
        st.info("No skills tracked yet. Complete onboarding to see your skill gaps.")
        return

    # Fetch gap data once and build a dict for O(1) lookups in chart building.
    try:
        gap_result = (
            client.table("mart_skill_gap_analysis")
            .select(
                "skill_display_name, demand_score, gap_score, gap_score_normalized, gap_rank"
            )
            .eq("user_id", user_id)
            .execute()
        )
        gap_rows: list[dict[str, Any]] = list(gap_result.data or [])
    except Exception as e:  # noqa: BLE001
        st.error(f"Could not load Top Skill Gaps: {e}")
        gap_rows = []

    gap_by_skill: dict[str, dict[str, Any]] = {}
    for row in gap_rows:
        key = row.get("skill_display_name")
        if key is None:
            continue
        gap_by_skill[str(key)] = row

    # Category grouping order (raw values) and their display labels.
    category_order = ["language", "framework", "tool", "concept", "soft_skill"]
    category_label_map = {
        "language": "Languages",
        "framework": "Frameworks",
        "tool": "Tools",
        "concept": "Concepts",
        "soft_skill": "Soft Skills",
    }

    # Build a chart per category.
    for category_raw in category_order:
        # Filter to the current user's skills for this category.
        category_skills = [r for r in chart_rows if r.get("category_raw") == category_raw]
        if not category_skills:
            continue

        # Sort skills by gap score descending (missing gap goes last).
        def _gap_norm_0_5(skill_row: dict[str, Any]) -> float:
            gap = gap_by_skill.get(skill_row["skill_display_name"])
            if not gap:
                return -1.0
            gap_norm_0_10 = gap.get("gap_score_normalized")
            if gap_norm_0_10 is None:
                return -1.0
            return float(gap_norm_0_10) / 2.0

        category_skills_sorted = sorted(category_skills, key=_gap_norm_0_5, reverse=True)
        ordered_skill_names = [r["skill_display_name"] for r in category_skills_sorted]

        # Prepare long-form data for Plotly grouped bar chart.
        records: list[dict[str, Any]] = []
        for r in category_skills_sorted:
            records.append(
                {
                    "skill": r["skill_display_name"],
                    "score": float(r["level"]),
                    "score_type": "Your level",
                }
            )
            gap = gap_by_skill.get(r["skill_display_name"])
            if gap:
                gap_norm_0_10 = gap.get("gap_score_normalized")
                if gap_norm_0_10 is not None:
                    records.append(
                        {
                            "skill": r["skill_display_name"],
                            "score": float(gap_norm_0_10) / 2.0,
                            "score_type": "Gap score",
                        }
                    )

        # Convert to DataFrame; maintain y-axis ordering via categorical dtype.
        chart_df = pd.DataFrame(records)
        if chart_df.empty:
            continue
        chart_df["skill"] = pd.Categorical(
            chart_df["skill"], categories=ordered_skill_names, ordered=True
        )

        # Section header (human-readable).
        st.markdown(f"### {category_label_map.get(category_raw, category_raw)}")

        # Compact chart sizing: 40px per skill row, minimum 120px.
        height = max(120, 40 * len(category_skills_sorted))

        # Two side-by-side bars per skill (grouped).
        figure = px.bar(
            chart_df,
            x="score",
            y="skill",
            orientation="h",
            color="score_type",
            barmode="group",
            color_discrete_map={
                "Your level": "#6366F1",
                "Gap score": "#F97316",
            },
        )
        figure.update_layout(
            height=height,
            margin=dict(l=0, r=0, t=0, b=0),
            showlegend=True,
        )
        figure.update_xaxes(range=[0, 5], dtick=1)
        st.plotly_chart(figure, use_container_width=True)

    # Keep the existing "Top Skill Gaps" table below the charts.
    if gap_rows:
        # Table should be ranked (gap_rank); reuse the same columns as before.
        gap_df = pd.DataFrame(gap_rows).sort_values("gap_rank").head(10)
        if not gap_df.empty and "gap_score_normalized" in gap_df.columns:
            gap_df = gap_df.rename(columns={"gap_score_normalized": "Gap score (0-10)"})
            keep_cols = [
                "gap_rank",
                "skill_display_name",
                "demand_score",
                "Gap score (0-10)",
            ]
            gap_df = gap_df[[c for c in keep_cols if c in gap_df.columns]]
    else:
        st.info("No skill gaps found yet.")
        gap_df = pd.DataFrame(
            columns=["gap_rank", "skill_display_name", "demand_score", "Gap score (0-10)"]
        )

    st.markdown("### Top Skill Gaps")
    st.dataframe(gap_df, use_container_width=True, hide_index=True)


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
