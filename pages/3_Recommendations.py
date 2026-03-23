"""Recommendations - Review and manage learning recommendations."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

import streamlit as st
from supabase import Client

from datapulse.streamlit_auth import get_authenticated_client

RecommendationStatus = Literal["pending", "approved", "rejected", "completed"]
PriorityTier = Literal["critical", "important", "nice_to_have"]


def _get_user_id() -> str:
    """Return current user_id from session state."""
    user = st.session_state.get("user") or {}
    user_id = user.get("id")
    if not user_id:
        st.warning("User identity is missing. Please log in again.")
        st.stop()
    return str(user_id)


def _parse_generated_at(value: Any) -> str:
    """Format generated_at for display (e.g. 'Mar 22, 2026')."""
    if not value:
        return "n/a"
    try:
        raw = str(value)
        normalized = raw.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt = dt.astimezone(timezone.utc)
        return dt.strftime("%b %d, %Y")
    except Exception:  # noqa: BLE001
        return str(value)


def _priority_badge_style(priority: str) -> tuple[str, str]:
    """Return (label, background_color) for priority tier badge."""
    p = (priority or "").strip()
    mapping = {
        "critical": ("Critical", "#EF4444"),  # red
        "important": ("Important", "#F97316"),  # orange
        "nice_to_have": ("Nice to have", "#9CA3AF"),  # gray
    }
    return mapping.get(p, ("Unknown", "#6B7280"))


def _count_status(client: Client, user_id: str, status: RecommendationStatus) -> int:
    """Count recommendations for one status."""
    try:
        result = (
            client.table("recommendations")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .eq("status", status)
            .execute()
        )
        return int(getattr(result, "count", 0) or 0)
    except Exception as e:  # noqa: BLE001
        st.error(f"Could not load count for status={status}: {e}")
        return 0


def render_header(client: Client, user_id: str) -> None:
    """Render page header and pending/approved/rejected metric counts."""
    st.title("Recommendations")
    st.caption("Review and act on your personalized learning suggestions")

    pending = _count_status(client, user_id, "pending")
    approved = _count_status(client, user_id, "approved")
    rejected = _count_status(client, user_id, "rejected")

    col1, col2, col3 = st.columns(3)
    col1.metric("Pending", pending)
    col2.metric("Approved", approved)
    col3.metric("Rejected", rejected)


def render_filters() -> tuple[str, str]:
    """Render the filter bar and return (status_filter, priority_filter)."""
    col_status, col_priority = st.columns(2)

    with col_status:
        status_label_to_value = {
            "All": "all",
            "Pending": "pending",
            "Approved": "approved",
            "Rejected": "rejected",
        }
        status_label = st.selectbox(
            "Status",
            options=list(status_label_to_value.keys()),
            index=0,
        )
        status_value = status_label_to_value[status_label]

    with col_priority:
        priority_label_to_value = {
            "All": "all",
            "Critical": "critical",
            "Important": "important",
            "Nice to have": "nice_to_have",
        }
        priority_label = st.selectbox(
            "Priority",
            options=list(priority_label_to_value.keys()),
            index=0,
        )
        priority_value = priority_label_to_value[priority_label]

    return status_value, priority_value


def _extract_skill_name(rec: dict[str, Any]) -> str:
    """Best-effort extraction of skill display name from a recommendation row."""
    # If nested select works, Supabase commonly returns a nested object under 'skills'.
    skills_obj = rec.get("skills")
    if isinstance(skills_obj, dict):
        return str(skills_obj.get("display_name") or skills_obj.get("name") or "Unknown skill")

    # Some Supabase responses may flatten nested fields with dot notation.
    display_name = rec.get("skills.display_name") or rec.get("skills.display_name".replace(".", "_"))
    if display_name:
        return str(display_name)
    name = rec.get("skills.name")
    if name:
        return str(name)

    # Fallback: if only skill_id is present, show the id.
    sid = rec.get("skill_id")
    if sid is not None:
        return str(sid)
    return "Unknown skill"


def render_recommendation_card(
    client: Client,
    user_id: str,
    rec: dict[str, Any],
) -> None:
    """Render one recommendation card with action buttons."""
    rid = rec.get("id")
    if rid is None:
        st.error("Recommendation row missing 'id'.")
        return

    status = str(rec.get("status") or "pending")
    priority_tier = str(rec.get("priority_tier") or "critical")
    priority_label, color = _priority_badge_style(priority_tier)
    skill_name = _extract_skill_name(rec)

    gap_rank = rec.get("gap_rank")
    generated_at = _parse_generated_at(rec.get("generated_at"))
    recommendation_text = str(rec.get("recommendation_text") or "").strip()

    # Render the card container.
    with st.container():
        # Card header row with skill name + priority badge.
        header_cols = st.columns([3, 1])
        with header_cols[0]:
            st.markdown(f"**{skill_name}**")
        with header_cols[1]:
            st.markdown(
                (
                    f"<span style='background-color:{color}; color:white; "
                    "padding:2px 10px; border-radius:999px; font-size:12px; font-weight:700;'>"
                    f"{priority_label}</span>"
                ),
                unsafe_allow_html=True,
            )

        st.caption(f"Status: {status.replace('_', ' ').title()}")
        st.write(recommendation_text if recommendation_text else "(No recommendation text.)")

        # Card footer row: gap rank + generated date, plus actions.
        footer_cols = st.columns([2, 3])
        with footer_cols[0]:
            gap_s = f"Gap rank: #{gap_rank}" if gap_rank is not None else "Gap rank: n/a"
            st.write(gap_s)
            st.write(f"Generated: {generated_at}")

        with footer_cols[1]:
            if status == "pending":
                # Approve / reject for pending recommendations.
                approve_key = f"approve_{rid}"
                reject_key = f"reject_{rid}"
                a_col, r_col = st.columns(2)
                with a_col:
                    if st.button("✓ Approve", key=approve_key, use_container_width=True):
                        try:
                            client.table("recommendations").update({"status": "approved"}).eq(
                                "id", rid
                            ).eq("user_id", user_id).execute()
                            st.rerun()
                        except Exception as e:  # noqa: BLE001
                            st.error(f"Could not approve recommendation: {e}")
                with r_col:
                    if st.button("✗ Reject", key=reject_key, use_container_width=True):
                        try:
                            client.table("recommendations").update({"status": "rejected"}).eq(
                                "id", rid
                            ).eq("user_id", user_id).execute()
                            st.rerun()
                        except Exception as e:  # noqa: BLE001
                            st.error(f"Could not reject recommendation: {e}")

            elif status in {"approved", "rejected"}:
                # Move back to pending for already decided recommendations.
                back_key = f"back_{rid}"
                if st.button("↩ Move to pending", key=back_key, use_container_width=True):
                    try:
                        client.table("recommendations").update({"status": "pending"}).eq(
                            "id", rid
                        ).eq("user_id", user_id).execute()
                        st.rerun()
                    except Exception as e:  # noqa: BLE001
                        st.error(f"Could not move recommendation back to pending: {e}")

            else:
                # Completed recommendations are informational only.
                st.caption("No actions available for completed recommendations.")


def render_recommendations_list(
    client: Client,
    user_id: str,
    status_filter: str,
    priority_filter: str,
) -> None:
    """Load and render the recommendations list based on current filters."""
    try:
        base_query = (
            client.table("recommendations")
            .select(
                "id, skill_id, recommendation_text, priority_tier, gap_rank, status, generated_at, "
                "skills(display_name, name)"
            )
            .eq("user_id", user_id)
        )

        if status_filter != "all":
            base_query = base_query.eq("status", status_filter)

        if priority_filter != "all":
            base_query = base_query.eq("priority_tier", priority_filter)

        result = (
            base_query.order("gap_rank").order("generated_at", desc=True).execute()
        )
        rec_rows: list[dict[str, Any]] = list(result.data or [])

    except Exception as e:  # noqa: BLE001
        # Fallback path: if join/nested select fails, still render by fetching skill_id.
        st.error(f"Could not load recommendations (join skills): {e}")
        try:
            base_query = (
                client.table("recommendations")
                .select("id, skill_id, recommendation_text, priority_tier, gap_rank, status, generated_at")
                .eq("user_id", user_id)
            )
            if status_filter != "all":
                base_query = base_query.eq("status", status_filter)
            if priority_filter != "all":
                base_query = base_query.eq("priority_tier", priority_filter)
            result = base_query.order("gap_rank").order("generated_at", desc=True).execute()
            rec_rows = list(result.data or [])

            # Load all skills in one query for display-name mapping.
            skill_ids = [str(r.get("skill_id")) for r in rec_rows if r.get("skill_id") is not None]
            skill_map: dict[str, str] = {}
            if skill_ids:
                skills_result = client.table("skills").select("id, display_name, name").in_("id", skill_ids).execute()
                for s in list(skills_result.data or []):
                    sid = s.get("id")
                    if sid is None:
                        continue
                    label = s.get("display_name") or s.get("name") or "Unknown skill"
                    skill_map[str(sid)] = str(label)

            for r in rec_rows:
                sid = r.get("skill_id")
                if sid is not None:
                    # Attach a lightweight nested object so _extract_skill_name works.
                    r["skills"] = {"display_name": skill_map.get(str(sid)), "name": None}
        except Exception as exc:  # noqa: BLE001
            st.error(f"Could not load recommendations (fallback): {exc}")
            return

    if not rec_rows:
        st.info("No recommendations match the selected filters.")
        return

    # Render cards with visual separation.
    for idx, rec in enumerate(rec_rows):
        render_recommendation_card(client, user_id, rec)
        if idx < len(rec_rows) - 1:
            st.divider()


def main() -> None:
    """Render the Recommendations page."""
    client = get_authenticated_client()
    user_id = _get_user_id()

    render_header(client, user_id)

    # Render filter bar and map UI selections to DB filters.
    status_filter, priority_filter = render_filters()

    # Batch action: show only when viewing Pending recommendations.
    if status_filter == "pending":
        if st.button("Approve all pending", key="approve_all_pending", use_container_width=True):
            try:
                client.table("recommendations").update({"status": "approved"}).eq("user_id", user_id).eq(
                    "status", "pending"
                ).execute()
                st.rerun()
            except Exception as e:  # noqa: BLE001
                st.error(f"Could not approve all pending: {e}")

    render_recommendations_list(client, user_id, status_filter, priority_filter)


if __name__ == "__main__":
    main()
