"""Reports - View generated career intelligence reports."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import streamlit as st

from datapulse.streamlit_auth import get_authenticated_client
from datapulse.ui.styles import inject_global_styles

inject_global_styles()


def render_reports_list() -> None:
    """Render the markdown reports list from `docs/reports/`."""
    reports_dir = Path(__file__).parent.parent / "docs" / "reports"
    empty_state_msg = (
        "No reports yet.\nReports are generated automatically every Sunday."
    )

    # Guard: directory might not exist (fresh installs) or might be empty.
    if not reports_dir.exists():
        st.info(empty_state_msg)
        return

    # List `.md` files and sort by filename descending (newest first).
    report_files = sorted(
        reports_dir.glob("*.md"),
        key=lambda p: p.name,
        reverse=True,
    )
    if not report_files:
        st.info(empty_state_msg)
        return

    # Render each report file in a consistent layout.
    for report_path in report_files:
        # Human-friendly title based on the filename.
        report_title = report_path.stem.replace("-", " ")

        try:
            # Render modification date for quick context.
            modified_dt = datetime.fromtimestamp(report_path.stat().st_mtime)
            modified_str = modified_dt.strftime("%Y-%m-%d %H:%M")

            # Load report contents once; reuse for expander + download.
            report_text = report_path.read_text(encoding="utf-8")
        except Exception as e:  # noqa: BLE001
            st.warning(f"Could not load report `{report_path.name}`: {e}")
            continue

        st.markdown(f"### {report_title}")
        st.write(f"Modified: {modified_str}")

        # Expandable section with markdown preview.
        with st.expander(report_title):
            st.markdown(report_text)

        # Download button with file contents.
        st.download_button(
            label="Download",
            data=report_text,
            file_name=report_path.name,
            mime="text/markdown",
            key=f"download-{report_path.name}",
        )


def main() -> None:
    """Render Reports page."""
    # Enforce the same authenticated-client pattern used across app pages.
    get_authenticated_client()

    st.title("Reports")
    st.subheader("Your weekly career intelligence reports")

    render_reports_list()


if __name__ == "__main__":
    main()
