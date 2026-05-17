"""Authenticated PostgREST helpers (explicit user JWT on each request)."""

from __future__ import annotations

from typing import Any

import httpx

from datapulse.config import get_supabase_anon_key, get_supabase_url


def insert_questions_bank_row(access_token: str, row: dict[str, Any]) -> None:
    """
    Insert one questions_bank row using the user JWT.

    Omits created_by so the DB default (auth.uid()) applies when migration 012
    has been applied. Raises httpx.HTTPStatusError on failure.
    """
    payload = {key: value for key, value in row.items() if key != "created_by"}
    base_url = get_supabase_url().rstrip("/")
    anon_key = get_supabase_anon_key()
    response = httpx.post(
        f"{base_url}/rest/v1/questions_bank",
        headers={
            "apikey": anon_key,
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
        json=payload,
        timeout=60.0,
    )
    response.raise_for_status()
