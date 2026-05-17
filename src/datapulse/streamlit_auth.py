"""Streamlit auth helpers for Supabase.

Supabase client objects are not reliably serializable across Streamlit script
reruns (and can be lost on direct navigation to `pages/`). This module
rebuilds an authenticated client from the session tokens every time.
"""

from __future__ import annotations

from typing import Final

import streamlit as st
from supabase import Client, create_client

from datapulse.config import get_supabase_anon_key, get_supabase_url

_SESSION_ACCESS_TOKEN: Final[str] = "access_token"
_SESSION_REFRESH_TOKEN: Final[str] = "refresh_token"
_SESSION_CLIENT_KEY: Final[str] = "supabase_user_client"


def bind_postgrest_user_jwt(client: Client, access_token: str) -> None:
    """Ensure PostgREST table/RPC calls send the user JWT for RLS (auth.uid())."""
    bearer = f"Bearer {access_token}"
    client.options.headers["Authorization"] = bearer
    client.auth._headers["Authorization"] = bearer
    client._storage = None
    client._functions = None
    # Eagerly (re)build PostgREST and set the bearer on its own header object.
    client._postgrest = None
    client.postgrest.auth(access_token)


def resolve_auth_user_id(client: Client, access_token: str) -> str:
    """Return auth.users id from the access token (JWT sub) and sync session user."""
    bind_postgrest_user_jwt(client, access_token)
    response = client.auth.get_user(access_token)
    user = response.user if response else None
    if user is None or not user.id:
        raise ValueError("Could not resolve authenticated user from access token.")
    user_id = str(user.id)
    st.session_state["user"] = {
        "id": user_id,
        "email": getattr(user, "email", None),
    }
    return user_id


def get_authenticated_client() -> Client:
    """
    Return a Supabase client authenticated with the current session tokens.

    Behavior:
    - Reads `access_token` and `refresh_token` from `st.session_state`.
    - If either is missing/None: shows a warning and stops the page.
    - Always rebuilds a fresh client with `create_client(url, anon_key)`.
    - Binds the tokens via `client.auth.set_session(...)`.
    - Updates `st.session_state.supabase_user_client` with the freshly
      authenticated client and returns it.

    This function never trusts a cached client object.
    """
    access_token = st.session_state.get(_SESSION_ACCESS_TOKEN)
    refresh_token = st.session_state.get(_SESSION_REFRESH_TOKEN)

    if access_token is None or refresh_token is None:
        st.warning("Please log in first.")
        st.stop()

    supabase_url = get_supabase_url().strip()
    anon_key = get_supabase_anon_key().strip()
    if not supabase_url or not anon_key:
        st.error(
            "Missing Supabase configuration. Set SUPABASE_URL and SUPABASE_ANON_KEY "
            "in Streamlit secrets or .env."
        )
        st.stop()

    client = create_client(supabase_url, anon_key)
    client.auth.set_session(access_token, refresh_token)
    try:
        resolve_auth_user_id(client, access_token)
    except ValueError:
        st.warning("Session expired or invalid. Please log in again.")
        st.stop()
    st.session_state[_SESSION_CLIENT_KEY] = client
    return client

