"""
downloads.py
Generates downloadable MD and PDF files from study_documentation and theory_content.
Used by the Downloads page. Pure Python — no system dependencies.
PDF generated via fpdf2.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from fpdf import FPDF
from supabase import Client


def _fetch_all_topics(client: Client) -> list[dict]:
    """Fetch all curriculum topics ordered by topic_number."""
    result = (
        client.table("curriculum_topics")
        .select("id, topic_number, title")
        .order("topic_number")
        .execute()
    )
    return result.data or []


def _fetch_theory(client: Client, topic_id: str) -> str | None:
    """Fetch pre-seeded theory content for a topic."""
    result = (
        client.table("theory_content")
        .select("content")
        .eq("topic_id", topic_id)
        .limit(1)
        .execute()
    )
    if result.data:
        return result.data[0]["content"]
    return None


def _fetch_study_doc(client: Client, user_id: str, topic_id: str) -> str | None:
    """Fetch user's study documentation for a topic."""
    result = (
        client.table("study_documentation")
        .select("content")
        .eq("user_id", user_id)
        .eq("topic_id", topic_id)
        .limit(1)
        .execute()
    )
    if result.data:
        return result.data[0]["content"]
    return None


def build_theory_md(topic_title: str, content: str) -> str:
    """Wrap theory content in a markdown document with header."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"# Theory: {topic_title}\n_Generated: {ts}_\n\n{content}"


def build_study_doc_md(topic_title: str, content: str) -> str:
    """Wrap study documentation in a markdown document with header."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"# Study Notes: {topic_title}\n_Last updated: {ts}_\n\n{content}"


def build_combined_md(
    user_display_name: str,
    topics: list[dict],
    theory_map: dict[str, str],
    study_doc_map: dict[str, str],
) -> str:
    """
    Build a single combined markdown document with all topics.
    Includes both theory and study notes per topic.
    """
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines = [
        f"# DataPulse Study Guide — {user_display_name}",
        f"_Generated: {ts}_",
        "",
        "---",
        "",
    ]
    for topic in topics:
        tid = str(topic["id"])
        title = topic["title"]
        lines.append(f"## {topic['topic_number']}. {title}")
        lines.append("")
        if theory_map.get(tid):
            lines.append("### Theory")
            lines.append(theory_map[tid])
            lines.append("")
        if study_doc_map.get(tid):
            lines.append("### My Study Notes")
            lines.append(study_doc_map[tid])
            lines.append("")
        lines.append("---")
        lines.append("")
    return "\n".join(lines)


def _md_to_pdf_bytes(title: str, markdown_content: str) -> bytes:
    """
    Convert markdown content to PDF bytes using fpdf2.
    Strips markdown formatting and sanitizes to latin-1 to avoid encoding errors.
    fpdf2 Helvetica font only supports latin-1 character range.
    """
    def _safe(text: str) -> str:
        """Replace characters outside latin-1 range with '?' to prevent encoding errors."""
        return text.encode("latin-1", errors="replace").decode("latin-1")

    def _break_long_words(text: str, max_len: int = 80) -> str:
        """Break words longer than max_len to prevent FPDF horizontal overflow."""
        return re.sub(
            r"(\S{" + str(max_len) + r",})",
            lambda m: "\n".join(
                [m.group(0)[i : i + max_len] for i in range(0, len(m.group(0)), max_len)]
            ),
            text,
        )

    pdf = FPDF()
    pdf.add_page()

    # Title — sanitized; reset X so multi_cell(0, ...) has full line width
    pdf.set_font("Helvetica", style="B", size=16)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(0, 10, _safe(title))
    pdf.ln(4)

    # Body — strip markdown symbols, sanitize, render line by line
    pdf.set_font("Helvetica", size=11)
    for line in markdown_content.splitlines():
        clean = re.sub(r"^#{1,6}\s*", "", line)
        clean = re.sub(r"\*{1,3}(.*?)\*{1,3}", r"\1", clean)
        clean = re.sub(r"`([^`]+)`", r"\1", clean)
        if clean.strip() in ("---", "***", "___"):
            pdf.ln(3)
            pdf.set_x(pdf.l_margin)
            continue
        clean = _break_long_words(clean)
        for subline in clean.splitlines():
            if pdf.w - pdf.x - pdf.r_margin < pdf.font_size:
                pdf.ln()
                pdf.set_x(pdf.l_margin)
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(0, 7, _safe(subline))

    return bytes(pdf.output())


def get_theory_pdf_bytes(topic_title: str, content: str) -> bytes:
    """Generate PDF bytes for a single topic's theory."""
    md = build_theory_md(topic_title, content)
    return _md_to_pdf_bytes(f"Theory: {topic_title}", md)


def get_study_doc_pdf_bytes(topic_title: str, content: str) -> bytes:
    """Generate PDF bytes for a single topic's study notes."""
    md = build_study_doc_md(topic_title, content)
    return _md_to_pdf_bytes(f"Study Notes: {topic_title}", md)


def get_combined_pdf_bytes(
    user_display_name: str,
    topics: list[dict],
    theory_map: dict[str, str],
    study_doc_map: dict[str, str],
) -> bytes:
    """Generate PDF bytes for the full combined study guide."""
    md = build_combined_md(user_display_name, topics, theory_map, study_doc_map)
    return _md_to_pdf_bytes(f"DataPulse Study Guide — {user_display_name}", md)


def fetch_all_data_for_user(
    client: Client, user_id: str, topics: list[dict]
) -> tuple[dict[str, str], dict[str, str]]:
    """
    Fetch theory and study docs for all topics.
    Returns (theory_map, study_doc_map) keyed by topic_id string.
    """
    theory_map: dict[str, str] = {}
    study_doc_map: dict[str, str] = {}
    for topic in topics:
        tid = str(topic["id"])
        theory = _fetch_theory(client, tid)
        if theory:
            theory_map[tid] = theory
        doc = _fetch_study_doc(client, user_id, tid)
        if doc:
            study_doc_map[tid] = doc
    return theory_map, study_doc_map
