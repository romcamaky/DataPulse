"""
One-time backfill: resolve skill_id for existing market_signals
that were inserted before alias normalization was complete.

Usage:
    python -m datapulse.backfill_skills           # live run
    python -m datapulse.backfill_skills --dry-run  # preview only
"""

from __future__ import annotations

import argparse
import logging
import re
from typing import Any

from datapulse.db import get_client
from datapulse.extractor import SkillIndex, load_skill_index
from datapulse.skill_aliases import SKILL_ALIASES

LOGGER = logging.getLogger("datapulse.backfill_skills")


def _normalize_display_key(display: str) -> str:
    """Lowercase and collapse whitespace for display-name equality checks."""
    return re.sub(r"\s+", " ", display.strip().lower())


def resolve_skill_id(skill_name_raw: str, index: SkillIndex) -> str | None:
    """Resolve a raw skill name to a canonical skill UUID.

    Mirrors the resolution logic in ``extractor.resolve_skill_id`` so that
    the backfill produces identical mappings for historical rows.

    Args:
        skill_name_raw: The free-text skill name from market_signals.
        index: Pre-built lookup index over the skills table.

    Returns:
        The skill UUID string if resolved, otherwise None.
    """
    raw = skill_name_raw.strip()
    if not raw:
        return None

    lower = raw.lower()

    # 1) Exact match on canonical name.
    if lower in index.by_name:
        return index.by_name[lower]

    # 2) Case-insensitive display_name match.
    norm_display = _normalize_display_key(raw)
    if norm_display in index.by_display_lower:
        return index.by_display_lower[norm_display]

    # 3) Alias lookup → canonical name → id.
    alias_key = re.sub(r"\s+", " ", lower)
    if alias_key in SKILL_ALIASES:
        target_name = SKILL_ALIASES[alias_key]
        return index.by_name.get(target_name)

    # 4) Compact underscore fallback (catches edge cases like "Apache Kafka" → apache_kafka).
    compact = re.sub(r"[^a-z0-9]+", "_", lower).strip("_")
    if compact in index.by_name:
        return index.by_name[compact]

    return None


def fetch_unmapped_signals(client: Any) -> list[dict[str, Any]]:
    """Fetch all market_signals rows where skill_id is NULL.

    Uses pagination to handle tables larger than PostgREST's default page size.

    Args:
        client: Supabase client instance.

    Returns:
        List of signal dicts with at least id, skill_name_raw, and skill_id fields.
    """
    page_size = 1000
    collected: list[dict[str, Any]] = []
    offset = 0

    while True:
        result = (
            client.table("market_signals")
            .select("id, skill_name_raw, skill_id")
            .is_("skill_id", "null")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        batch = result.data or []
        if not batch:
            break
        collected.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size

    return collected


def run_backfill(*, dry_run: bool) -> None:
    """Execute the backfill: load skills, resolve aliases, batch-update rows.

    Args:
        dry_run: If True, log what would change without writing to the database.
    """
    client = get_client()

    # Build the skill index from the current skills table (including newly inserted rows).
    skills_result = client.table("skills").select("id, name, display_name").execute()
    skills_rows = skills_result.data or []
    index = load_skill_index(skills_rows)
    LOGGER.info("Loaded %d canonical skills for backfill mapping", len(skills_rows))

    # Fetch all signals that still have NULL skill_id.
    unmapped = fetch_unmapped_signals(client)
    LOGGER.info("Found %d market_signals with NULL skill_id", len(unmapped))

    if not unmapped:
        LOGGER.info("Nothing to backfill — all signals already have a skill_id.")
        return

    # Resolve each signal and group updates by target skill_id for batch writes.
    resolved_count = 0
    still_unmapped_count = 0
    still_unmapped_names: set[str] = set()
    updates: dict[str, list[str]] = {}  # skill_id → [signal_id, ...]

    for signal in unmapped:
        raw_name = signal.get("skill_name_raw") or ""
        signal_id = str(signal["id"])
        skill_id = resolve_skill_id(raw_name, index)

        if skill_id:
            updates.setdefault(skill_id, []).append(signal_id)
            resolved_count += 1
        else:
            still_unmapped_count += 1
            still_unmapped_names.add(raw_name)

    LOGGER.info(
        "Resolution results: %d newly mapped, %d still unmapped",
        resolved_count,
        still_unmapped_count,
    )

    if dry_run:
        LOGGER.info("[dry-run] Would update %d signal(s) across %d skill(s)", resolved_count, len(updates))
        for skill_id, signal_ids in sorted(updates.items(), key=lambda x: -len(x[1])):
            LOGGER.info("[dry-run]   skill_id=%s → %d signal(s)", skill_id, len(signal_ids))
        if still_unmapped_names:
            LOGGER.info(
                "[dry-run] Still unmapped skill_name_raw values (%d unique): %s",
                len(still_unmapped_names),
                sorted(still_unmapped_names),
            )
        return

    # Batch update: one Supabase call per skill_id (groups of signal IDs).
    batch_count = 0
    for skill_id, signal_ids in updates.items():
        try:
            client.table("market_signals").update({"skill_id": skill_id}).in_(
                "id", signal_ids
            ).execute()
            batch_count += 1
        except Exception as exc:
            LOGGER.error(
                "Failed to update %d signals for skill_id=%s: %s",
                len(signal_ids),
                skill_id,
                exc,
            )

    LOGGER.info(
        "Backfill complete: %d signal(s) updated in %d batch(es), %d still unmapped",
        resolved_count,
        batch_count,
        still_unmapped_count,
    )
    if still_unmapped_names:
        LOGGER.info(
            "Still unmapped skill_name_raw values (%d unique): %s",
            len(still_unmapped_names),
            sorted(still_unmapped_names),
        )


def main() -> None:
    """CLI entry point for the backfill script."""
    parser = argparse.ArgumentParser(
        description="Backfill skill_id for market_signals with NULL skill_id.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing to the database.",
    )
    args = parser.parse_args()

    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="%(levelname)s %(name)s: %(message)s",
        )

    run_backfill(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
