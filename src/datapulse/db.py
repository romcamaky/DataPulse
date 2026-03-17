"""
DataPulse database client — Supabase connection.
Singleton pattern: call get_client() from any module to get the shared client.
Reused by onboarding, market agent, report generator, and CLI tool.
"""

from __future__ import annotations

from typing import Optional

from supabase import Client, create_client

from datapulse.config import SUPABASE_KEY, SUPABASE_URL


# Using service role key (bypasses RLS) for development.
# In Module 5, we switch to user JWT tokens from Supabase Auth
# so each user's queries are RLS-scoped automatically.
_client: Optional[Client] = None


def get_client() -> Client:
    """
    Get the shared Supabase client instance for the application.

    This function implements a simple singleton pattern: the Supabase client
    is created on first use and then reused for all subsequent calls within
    the current process.

    Returns:
        Client: An initialized Supabase Python client.

    Raises:
        RuntimeError: If the client cannot be initialized for any reason.
    """
    global _client

    if _client is not None:
        return _client

    try:
        # Create the Supabase client using the configured URL and service role key.
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
        return _client
    except Exception as exc:  # noqa: BLE001
        # Wrap any low-level exception in a clear, actionable error message.
        raise RuntimeError(
            "Failed to initialize Supabase client. "
            "Check your SUPABASE_URL and SUPABASE_KEY values in the .env file."
        ) from exc

