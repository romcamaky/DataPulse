"""
6_Downloads.py
Download study materials — theory and personal study notes.
Per-topic or combined across all topics. MD and PDF formats.
"""

from __future__ import annotations

import streamlit as st

from datapulse.downloads import (
    _fetch_all_topics,
    build_combined_md,
    build_study_doc_md,
    build_theory_md,
    fetch_all_data_for_user,
    get_combined_pdf_bytes,
    get_study_doc_pdf_bytes,
    get_theory_pdf_bytes,
)
from datapulse.streamlit_auth import get_authenticated_client
from datapulse.ui.styles import inject_global_styles

inject_global_styles()


def _get_user_id_or_stop() -> str:
    user = st.session_state.get("user")
    if not user:
        st.warning("Please log in first.")
        st.stop()
    return str(user["id"])


def _get_display_name() -> str:
    user = st.session_state.get("user") or {}
    return user.get("display_name") or user.get("email") or "user"


def main() -> None:
    st.title("⬇️ Downloads")
    st.caption("Download your theory notes and study documentation as Markdown or PDF.")

    client = get_authenticated_client()
    user_id = _get_user_id_or_stop()
    display_name = _get_display_name()

    topics = _fetch_all_topics(client)
    if not topics:
        st.error("No topics found.")
        return

    # Load all data once (cached in session for this page load)
    with st.spinner("Loading your materials..."):
        theory_map, study_doc_map = fetch_all_data_for_user(client, user_id, topics)

    # ── Combined downloads ────────────────────────────────────────────────────
    st.subheader("📦 Complete Study Guide")
    st.caption("All topics combined into one file.")

    combined_md = build_combined_md(display_name, topics, theory_map, study_doc_map)
    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            label="⬇️ Download MD",
            data=combined_md,
            file_name="datapulse_study_guide.md",
            mime="text/markdown",
            use_container_width=True,
        )
    with col2:
        pdf_bytes = get_combined_pdf_bytes(display_name, topics, theory_map, study_doc_map)
        st.download_button(
            label="⬇️ Download PDF",
            data=pdf_bytes,
            file_name="datapulse_study_guide.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

    st.divider()

    # ── Per-topic downloads ───────────────────────────────────────────────────
    st.subheader("📄 Per-Topic Downloads")

    topic_options = {f"{t['topic_number']}. {t['title']}": t for t in topics}
    selected_label = st.selectbox("Select topic:", list(topic_options.keys()))
    selected_topic = topic_options[selected_label]
    tid = str(selected_topic["id"])
    title = selected_topic["title"]
    safe_title = title.lower().replace(" ", "_").replace("&", "and")

    theory_content = theory_map.get(tid)
    study_doc_content = study_doc_map.get(tid)

    # Theory downloads
    st.markdown("**Theory**")
    if theory_content:
        t_md = build_theory_md(title, theory_content)
        c1, c2 = st.columns(2)
        with c1:
            st.download_button(
                label="⬇️ MD",
                data=t_md,
                file_name=f"theory_{safe_title}.md",
                mime="text/markdown",
                use_container_width=True,
                key=f"theory_md_{tid}",
            )
        with c2:
            st.download_button(
                label="⬇️ PDF",
                data=get_theory_pdf_bytes(title, theory_content),
                file_name=f"theory_{safe_title}.pdf",
                mime="application/pdf",
                use_container_width=True,
                key=f"theory_pdf_{tid}",
            )
    else:
        st.caption("No theory available for this topic.")

    # Study notes downloads
    st.markdown("**My Study Notes**")
    if study_doc_content:
        d_md = build_study_doc_md(title, study_doc_content)
        c1, c2 = st.columns(2)
        with c1:
            st.download_button(
                label="⬇️ MD",
                data=d_md,
                file_name=f"notes_{safe_title}.md",
                mime="text/markdown",
                use_container_width=True,
                key=f"notes_md_{tid}",
            )
        with c2:
            st.download_button(
                label="⬇️ PDF",
                data=get_study_doc_pdf_bytes(title, study_doc_content),
                file_name=f"notes_{safe_title}.pdf",
                mime="application/pdf",
                use_container_width=True,
                key=f"notes_pdf_{tid}",
            )
    else:
        st.caption(
            "No study notes yet for this topic. Complete a Lab session or Learn session to generate them."
        )


if __name__ == "__main__":
    main()
