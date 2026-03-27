"""Shared Streamlit CSS theme helpers for DataPulse UI."""

from __future__ import annotations

import streamlit as st


def inject_global_styles() -> None:
    """
    Inject global CSS styles and Google Fonts into the Streamlit app.

    Call this once at the top of each page, after st.set_page_config() when present.
    """
    html_block = """
        <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
        <style>
        /* Base typography: keep text consistent without overriding widget layout internals. */
        html, body, .stApp {
            font-family: "DM Sans", sans-serif !important;
            color: #1E293B;
        }
        .stApp p, .stApp li, .stApp label, .stApp [data-testid="stMarkdownContainer"] {
            font-size: 16px;
            line-height: 1.6;
        }

        /* Code typography: use monospace for technical snippets and badges. */
        code, pre, .stCode, .stCodeBlock, .tech-badge {
            font-family: "JetBrains Mono", monospace !important;
        }

        /* Sidebar visual treatment: card-like white panel with subtle border. */
        section[data-testid="stSidebar"] {
            background-color: #FFFFFF !important;
            border-right: 1px solid #E2E8F0;
        }
        section[data-testid="stSidebar"] * {
            font-size: 14px;
        }

        /* Metric cards: emphasize key KPIs with soft borders and spacing. */
        div[data-testid="stMetric"] {
            background: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 8px;
            padding: 0.75rem 1rem;
        }

        /* Dataframe headers: match teal brand tint for scanability. */
        .stDataFrame [data-testid="stTable"] thead tr th,
        .stDataFrame [role="columnheader"] {
            background-color: #F0FDFA !important;
            color: #0D9488 !important;
        }

        /* Primary buttons: branded teal with darker hover state. */
        .stButton > button {
            background-color: #14B8A6 !important;
            color: #FFFFFF !important;
            border: none !important;
            border-radius: 6px !important;
        }
        .stButton > button:hover {
            background-color: #0D9488 !important;
            color: #FFFFFF !important;
        }

        /* Keep expander headers readable when global font rules are active. */
        [data-testid="stExpander"] summary,
        [data-testid="stExpander"] button {
            line-height: normal !important;
        }

        /* Alert boxes: align success/info/warning with DataPulse palette. */
        [data-testid="stAlert"][kind="success"] {
            background-color: #F0FDFA !important;
            color: #0F766E !important;
            border: 1px solid #14B8A6 !important;
        }
        [data-testid="stAlert"][kind="info"] {
            background-color: #EFF6FF !important;
            color: #1E40AF !important;
            border: 1px solid #60A5FA !important;
        }
        [data-testid="stAlert"][kind="warning"] {
            background-color: #FFFBEB !important;
            color: #92400E !important;
            border: 1px solid #B4864D !important;
        }

        /* Utility card class for custom markdown containers. */
        .card {
            background: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 12px;
            padding: 1.5rem;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
        }
        </style>
        """

    # Prefer st.html when available so CSS is injected as raw HTML, not markdown text.
    if hasattr(st, "html"):
        st.html(html_block)
        return

    # Fallback for older Streamlit versions.
    st.markdown(html_block, unsafe_allow_html=True)
