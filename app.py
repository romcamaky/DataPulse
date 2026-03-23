"""
DataPulse - Personal AI Career Intelligence Platform.

Main Streamlit application entry point.
Handles authentication and page routing.
"""

from __future__ import annotations

from typing import Any

import streamlit as st
from supabase import Client, create_client

from datapulse.config import get_supabase_anon_key, get_supabase_url

# Page config must be the first Streamlit command.
st.set_page_config(
    page_title="DataPulse",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _session_defaults() -> None:
    """Initialize auth-related state values once per browser session."""
    if "access_token" not in st.session_state:
        st.session_state.access_token = None
    if "refresh_token" not in st.session_state:
        st.session_state.refresh_token = None
    if "user" not in st.session_state:
        st.session_state.user = None
    if "supabase_user_client" not in st.session_state:
        st.session_state.supabase_user_client = None


def _build_public_client() -> Client:
    """Create a Supabase client with anon credentials for auth operations."""
    supabase_url = get_supabase_url().strip()
    supabase_anon_key = get_supabase_anon_key().strip()

    if not supabase_url or not supabase_anon_key:
        st.error(
            "Missing Supabase configuration. Set SUPABASE_URL and SUPABASE_ANON_KEY "
            "in Streamlit secrets or .env."
        )
        st.stop()
    return create_client(supabase_url, supabase_anon_key)


def _extract_user_payload(user_obj: Any) -> dict[str, Any]:
    """Normalize a Supabase user object to a plain dict for session state."""
    if user_obj is None:
        return {}
    if isinstance(user_obj, dict):
        return user_obj
    if hasattr(user_obj, "model_dump"):
        return user_obj.model_dump()
    return {"email": getattr(user_obj, "email", None), "id": getattr(user_obj, "id", None)}


def _store_auth_state(auth_response: Any, client: Client) -> None:
    """Save tokens and user data after successful login or registration."""
    session = getattr(auth_response, "session", None)
    user = getattr(auth_response, "user", None)

    access_token = getattr(session, "access_token", None) if session else None
    refresh_token = getattr(session, "refresh_token", None) if session else None

    st.session_state.access_token = access_token
    st.session_state.refresh_token = refresh_token
    st.session_state.user = _extract_user_payload(user)

    # Keep a client bound to the authenticated session for RLS-scoped queries.
    if access_token and refresh_token:
        client.auth.set_session(access_token, refresh_token)
        st.session_state.supabase_user_client = client
    else:
        st.session_state.supabase_user_client = None


def _logout() -> None:
    """Clear all auth state and return to the login screen."""
    st.session_state.access_token = None
    st.session_state.refresh_token = None
    st.session_state.user = None
    st.session_state.supabase_user_client = None
    st.rerun()


def _render_auth_forms(client: Client) -> None:
    """Render login/register tabs for unauthenticated users."""
    st.title("📊 DataPulse")
    st.caption("Personal AI Career Intelligence Platform")

    login_tab, register_tab = st.tabs(["Login", "Register"])

    with login_tab:
        with st.form("login_form"):
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Password", type="password", key="login_password")
            submitted = st.form_submit_button("Login", use_container_width=True)

            if submitted:
                if not email or not password:
                    st.error("Please enter both email and password.")
                else:
                    try:
                        response = client.auth.sign_in_with_password(
                            {"email": email.strip(), "password": password}
                        )
                        if not getattr(response, "session", None):
                            st.error("Login failed. Please check your credentials.")
                        else:
                            _store_auth_state(response, client)
                            st.success("Logged in successfully.")
                            st.rerun()
                    except Exception as exc:  # noqa: BLE001
                        st.error(f"Login failed: {exc}")

    with register_tab:
        with st.form("register_form"):
            email = st.text_input("Email", key="register_email")
            password = st.text_input("Password", type="password", key="register_password")
            submitted = st.form_submit_button("Register", use_container_width=True)

            if submitted:
                if not email or not password:
                    st.error("Please enter both email and password.")
                else:
                    try:
                        response = client.auth.sign_up(
                            {"email": email.strip(), "password": password}
                        )
                        _store_auth_state(response, client)
                        st.success(
                            "Registration successful. If email confirmation is enabled, "
                            "check your inbox before logging in."
                        )
                        if st.session_state.access_token:
                            st.rerun()
                    except Exception as exc:  # noqa: BLE001
                        st.error(f"Registration failed: {exc}")


def _ensure_user_session(client: Client) -> None:
    """Rehydrate user object from token when needed."""
    access_token = st.session_state.get("access_token")
    if not access_token:
        return

    # If user information already exists, keep it.
    if st.session_state.get("user"):
        return

    try:
        response = client.auth.get_user(access_token)
        user = getattr(response, "user", None)
        st.session_state.user = _extract_user_payload(user)
    except Exception:  # noqa: BLE001
        # Token is invalid/expired; force a clean login.
        _logout()


def _render_authenticated_shell() -> None:
    """Render app home page and sidebar controls for authenticated users."""
    st.sidebar.success("Authenticated")
    user_email = (st.session_state.get("user") or {}).get("email", "User")
    st.sidebar.write(f"Signed in as: {user_email}")
    if st.sidebar.button("Logout", use_container_width=True):
        _logout()

    st.title("Welcome to DataPulse")
    st.write("Use the sidebar pages to navigate Dashboard, Learning Lab, Recommendations, and Reports.")
    st.info("Module 5 Phase 1 skeleton is active. Feature pages will be expanded in upcoming phases.")


def main() -> None:
    """Run the Streamlit application."""
    _session_defaults()
    supabase_client = _build_public_client()
    _ensure_user_session(supabase_client)

    if not st.session_state.get("access_token"):
        _render_auth_forms(supabase_client)
        return

    _render_authenticated_shell()


if __name__ == "__main__":
    main()
