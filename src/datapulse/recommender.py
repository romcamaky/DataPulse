"""
Personalized learning recommendations: gap marts + profile context → Claude Sonnet → ``recommendations``.

One API call per user; replaces prior ``pending`` rows for that user on each successful run.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Final

from anthropic import Anthropic
from anthropic import APIConnectionError, APIError, RateLimitError

from datapulse.config import get_anthropic_api_key
from datapulse.extractor import extract_json_array_from_response

LOGGER = logging.getLogger("datapulse.recommender")

# Sonnet for richer personalization than Haiku (single call per user; cost controlled).
_CLAUDE_MODEL: Final[str] = "claude-sonnet-4-20250514"
_MAX_TOKENS: Final[int] = 4096
_RETRY_BACKOFF_SEC: Final[float] = 5.0

_GAP_LIMIT: Final[int] = 25
_TREND_LIMIT: Final[int] = 10

_ALLOWED_RESOURCE_TYPES: Final[frozenset[str]] = frozenset(
    {
        "course",
        "tutorial",
        "project",
        "book",
        "podcast",
        "documentation",
        "practice",
        "certification",
    }
)
_ALLOWED_PRIORITY_TIERS: Final[frozenset[str]] = frozenset(
    {"critical", "important", "nice_to_have"}
)

_SYSTEM_PROMPT: Final[str] = """You are a career intelligence advisor for data professionals. You analyze a user's skill gaps against market demand and generate specific, actionable learning recommendations.

You must return ONLY a JSON array. Each element represents one recommendation:
{
  "skill_name": "Python",
  "gap_rank": 7,
  "priority_tier": "important",
  "recommendation_text": "Your Python is at level 2 but market demand is high (score 11.2). Focus on Pandas for data manipulation — it's the bridge from SQL-based analysis to Python-based pipelines. Start with the official 10 Minutes to Pandas tutorial, then build a small project converting one of your Power BI data prep steps to a Pandas script.",
  "resource_type": "tutorial",
  "resource_url": "https://pandas.pydata.org/docs/user_guide/10min.html",
  "estimated_hours": 8
}

Rules:
- Generate 1-2 recommendations per critical gap (top 5), 1 per important gap (ranks 6-15)
- Total recommendations: 10-20 per batch
- recommendation_text must be personalized: reference the user's current level, their background, their learning preferences, and their time budget
- resource_type: one of "course", "tutorial", "project", "book", "podcast", "documentation", "practice", "certification"
- resource_url: include when you know a specific, real resource. Use null if recommending a general approach
- estimated_hours: realistic estimate for someone at the user's current level
- Match resource types to user's learning_preferences (e.g., if they prefer "hands-on projects", recommend projects over courses)
- Respect weekly_hours_available — don't recommend a 40-hour course to someone with 3 hours/week
- If the user has listed platforms they have access to (e.g., Udemy, Coursera), prefer resources on those platforms
- If the user has documented learning failures, avoid recommending similar approaches
- Reference trending skills from the trend data to add urgency where relevant
- For users targeting specific roles, frame recommendations in terms of that role's requirements
- NEVER recommend LangChain, CrewAI, or similar orchestration frameworks — plain Python + Claude API is simpler, cheaper, and explainable for this user's level
- NEVER recommend Apache Airflow or Prefect for orchestration — GitHub Actions handles scheduling in this project
- NEVER recommend FastAPI — Supabase IS the backend; a separate API layer adds unnecessary complexity
- NEVER recommend job board scraping tools or approaches — legally risky and technically fragile
- Prefer free resources and resources on platforms the user has access to
- For AI/LLM topics, recommend Anthropic documentation and Claude API first, OpenAI second
- Keep recommendations practical and buildable — "build X with Y" over "study the theory of Z"
"""


@dataclass
class RecommenderRunStats:
    """Aggregates for logging at end of a recommender run."""

    users_considered: int = 0
    users_succeeded: int = 0
    users_skipped_no_gaps: int = 0
    users_skipped_no_profile: int = 0
    users_json_error: int = 0
    users_api_error: int = 0
    recommendations_inserted: int = 0
    recommendations_skipped_invalid: int = 0
    unmapped_skill_warnings: int = 0
    per_user_counts: dict[str, int] = field(default_factory=dict)


def _normalize_skill_key(name: str) -> str:
    """Lowercase and collapse whitespace for matching Claude ``skill_name`` to gap rows."""
    return re.sub(r"\s+", " ", name.strip().lower())


def _format_json_field(value: Any) -> str:
    """Pretty-print JSON-friendly profile fields for the prompt."""
    if value is None:
        return "n/a"
    if isinstance(value, (dict, list)):
        try:
            return json.dumps(value, ensure_ascii=False)
        except (TypeError, ValueError):
            return str(value)
    return str(value)


def _format_learning_preferences(prefs: Any) -> str:
    """Turn ``learning_preferences`` (array or scalar) into a readable line."""
    if prefs is None:
        return "n/a"
    if isinstance(prefs, list):
        return ", ".join(str(x) for x in prefs) if prefs else "n/a"
    return str(prefs)


def build_gap_skill_lookup(gaps: list[dict[str, Any]]) -> dict[str, str | None]:
    """
    Map normalized ``skill_display_name`` from gap analysis to ``skill_id`` (or ``None``).

    Used to resolve Claude's ``skill_name`` to canonical IDs when the mart has an id.
    """
    out: dict[str, str | None] = {}
    for row in gaps:
        sid = row.get("skill_id")
        display = row.get("skill_display_name")
        if not isinstance(display, str) or not display.strip():
            continue
        key = _normalize_skill_key(display)
        out[key] = str(sid) if sid is not None else None
    return out


def fetch_user_ids_with_gaps(client: Any) -> list[str]:
    """
    Return distinct ``user_id`` values present in ``mart_skill_gap_analysis``.

    Note: PostgREST may cap page size; for very large marts, extend with pagination.
    """
    result = client.table("mart_skill_gap_analysis").select("user_id").execute()
    raw = result.data or []
    seen: set[str] = set()
    for row in raw:
        uid = row.get("user_id")
        if uid is not None:
            seen.add(str(uid))
    return sorted(seen)


def fetch_gap_analysis(
    client: Any,
    user_id: str,
    *,
    limit: int = _GAP_LIMIT,
) -> list[dict[str, Any]]:
    """Load top gaps for ``user_id`` ordered by ``gap_rank`` ascending (1 = highest priority)."""
    result = (
        client.table("mart_skill_gap_analysis")
        .select(
            "skill_id, skill_display_name, user_level, demand_score, gap_score, "
            "gap_rank, gap_category, priority_tier, signal_count"
        )
        .eq("user_id", user_id)
        .order("gap_rank")
        .limit(limit)
        .execute()
    )
    return list(result.data or [])


def fetch_trend_summary(client: Any, *, limit: int = _TREND_LIMIT) -> list[dict[str, Any]]:
    """Load top market trends by ``trending_score`` for the prompt context."""
    result = (
        client.table("mart_trend_summary")
        .select(
            "skill_display_name, skill_category, signal_count, avg_strength, "
            "dominant_signal_type, trending_score"
        )
        .order("trending_score", desc=True)
        .limit(limit)
        .execute()
    )
    return list(result.data or [])


def fetch_user_profile(client: Any, user_id: str) -> dict[str, Any] | None:
    """
    Load profile fields needed for the prompt.

    Returns ``None`` if no row exists for ``user_id``.
    """
    result = (
        client.table("user_profiles")
        .select(
            "display_name, role_title, industry, country, years_total_experience, "
            "weekly_hours_available, learning_preferences, career_narrative, "
            "ai_usage_frequency, ai_api_experience, platform_access, "
            "course_completion_rate, learning_failures, work_frustrations"
        )
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    rows = result.data or []
    if not rows:
        return None
    return dict(rows[0])


def fetch_target_roles(client: Any, user_id: str) -> list[dict[str, Any]]:
    """Load target roles for ``user_id``, ordered by priority."""
    result = (
        client.table("user_target_roles")
        .select("role_name, priority, timeline, market_scope")
        .eq("user_id", user_id)
        .order("priority")
        .execute()
    )
    return list(result.data or [])


def build_user_message(
    *,
    profile: dict[str, Any],
    target_roles: list[dict[str, Any]],
    gaps: list[dict[str, Any]],
    trends: list[dict[str, Any]],
) -> str:
    """Assemble the user prompt block from DB-backed context."""
    display_name = profile.get("display_name") or "n/a"
    role_title = profile.get("role_title") or "n/a"
    industry = profile.get("industry") or "n/a"
    country = profile.get("country") or "n/a"
    years = profile.get("years_total_experience")
    years_s = str(years) if years is not None else "n/a"
    weekly = profile.get("weekly_hours_available")
    weekly_s = str(weekly) if weekly is not None else "n/a"
    prefs = _format_learning_preferences(profile.get("learning_preferences"))
    course_rate = profile.get("course_completion_rate") or "n/a"
    learning_failures = profile.get("learning_failures") or "n/a"
    work_frustrations = profile.get("work_frustrations") or "n/a"
    ai_usage = profile.get("ai_usage_frequency") or "n/a"
    ai_api = profile.get("ai_api_experience") or "n/a"
    platform_access = _format_json_field(profile.get("platform_access"))
    narrative = profile.get("career_narrative") or "n/a"

    lines: list[str] = [
        "Generate personalized learning recommendations for this user.",
        "",
        "## User Profile",
        f"Name: {display_name}",
        f"Current role: {role_title}",
        f"Industry: {industry}",
        f"Country: {country}",
        f"Experience: {years_s} years total",
        f"Weekly learning budget: {weekly_s} hours",
        f"Learning preferences: {prefs}",
        f"Course completion rate: {course_rate}",
        f"Past learning difficulties: {learning_failures}",
        f"Work frustrations: {work_frustrations}",
        f"AI experience: {ai_usage}, API level: {ai_api}",
        f"Platform access: {platform_access}",
        f"Career narrative: {narrative}",
        "",
        "## Target Roles",
    ]

    if not target_roles:
        lines.append("(none specified)")
    else:
        for tr in target_roles:
            rname = tr.get("role_name") or "Unknown role"
            pri = tr.get("priority")
            pri_s = str(pri) if pri is not None else "?"
            tl = tr.get("timeline") or "n/a"
            scope = tr.get("market_scope") or "n/a"
            lines.append(f"- {rname} (priority {pri_s}, timeline: {tl}, scope: {scope})")

    lines.extend(["", "## Skill Gaps (ranked by gap_score)", ""])

    for row in gaps:
        rank = row.get("gap_rank")
        name = row.get("skill_display_name") or "n/a"
        ul = row.get("user_level")
        demand = row.get("demand_score")
        gapz = row.get("gap_score")
        cat = row.get("gap_category") or "n/a"
        lines.append(
            f"{rank}. {name} — user level: {ul}/5, market demand: {demand}, "
            f"gap: {gapz}, category: {cat}"
        )

    lines.extend(["", "## Current Market Trends (top 10)", ""])

    for row in trends:
        name = row.get("skill_display_name") or "n/a"
        sig = row.get("signal_count")
        avg_s = row.get("avg_strength")
        tscore = row.get("trending_score")
        lines.append(
            f"{name} — signals: {sig}, avg_strength: {avg_s}, trending_score: {tscore}"
        )

    return "\n".join(lines).strip()


def call_claude_sonnet(anthropic_client: Anthropic, *, user_message: str) -> str:
    """
    Invoke Claude Sonnet with one retry on transient API errors.

    Raises on final failure so the caller can count API errors and skip the user.
    """
    for attempt in range(2):
        try:
            msg = anthropic_client.messages.create(
                model=_CLAUDE_MODEL,
                max_tokens=_MAX_TOKENS,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )
            blocks = msg.content
            if not blocks:
                raise RuntimeError("Empty response content from Claude")
            texts: list[str] = []
            for block in blocks:
                if hasattr(block, "text"):
                    texts.append(block.text)
                elif isinstance(block, dict) and block.get("type") == "text":
                    texts.append(str(block.get("text", "")))
            return "\n".join(texts).strip()
        except (APIConnectionError, RateLimitError, APIError, TimeoutError, OSError) as exc:
            LOGGER.warning(
                "Claude API attempt %d failed: %s", attempt + 1, exc, exc_info=False
            )
            if attempt == 0:
                time.sleep(_RETRY_BACKOFF_SEC)
                continue
            raise


def validate_recommendation_row(
    raw: dict[str, Any],
    *,
    gap_lookup: dict[str, str | None],
    stats: RecommenderRunStats,
) -> dict[str, Any] | None:
    """
    Validate one recommendation object; return DB row payload or ``None`` to skip.

    Resolves ``skill_id`` from ``skill_name`` using gap analysis; logs if unmapped.
    """
    skill_name = raw.get("skill_name")
    if not isinstance(skill_name, str) or not skill_name.strip():
        LOGGER.warning("Skipped recommendation: missing skill_name in %s", raw)
        return None

    rec_text = raw.get("recommendation_text")
    if not isinstance(rec_text, str) or not rec_text.strip():
        LOGGER.warning("Skipped recommendation: missing recommendation_text for %s", skill_name)
        return None

    rt = raw.get("resource_type")
    if not isinstance(rt, str) or rt not in _ALLOWED_RESOURCE_TYPES:
        LOGGER.warning("Skipped recommendation: invalid resource_type %r for %s", rt, skill_name)
        return None

    pt = raw.get("priority_tier")
    if not isinstance(pt, str) or pt not in _ALLOWED_PRIORITY_TIERS:
        LOGGER.warning("Skipped recommendation: invalid priority_tier %r for %s", pt, skill_name)
        return None

    key = _normalize_skill_key(skill_name)
    if key not in gap_lookup:
        LOGGER.warning(
            "skill_name %r does not match any gap skill_display_name; inserting with skill_id=null",
            skill_name,
        )
        stats.unmapped_skill_warnings += 1
        skill_id = None
    else:
        skill_id = gap_lookup[key]

    gap_rank_raw = raw.get("gap_rank")
    gap_rank: int | None
    try:
        if gap_rank_raw is None:
            gap_rank = None
        else:
            gap_rank = int(gap_rank_raw)
    except (TypeError, ValueError):
        LOGGER.warning("Skipped recommendation: invalid gap_rank for %s", skill_name)
        return None

    est_raw = raw.get("estimated_hours")
    est: int | None
    try:
        if est_raw is None:
            est = None
        else:
            est = int(est_raw)
    except (TypeError, ValueError):
        LOGGER.warning("Skipped recommendation: invalid estimated_hours for %s", skill_name)
        return None

    url_raw = raw.get("resource_url")
    resource_url: str | None
    if url_raw is None or (isinstance(url_raw, str) and not url_raw.strip()):
        resource_url = None
    elif isinstance(url_raw, str):
        resource_url = url_raw.strip()
    else:
        LOGGER.warning("Skipped recommendation: invalid resource_url for %s", skill_name)
        return None

    return {
        "skill_id": skill_id,
        "gap_rank": gap_rank,
        "priority_tier": pt,
        "recommendation_text": rec_text.strip(),
        "resource_type": rt,
        "resource_url": resource_url,
        "estimated_hours": est,
    }


def delete_pending_recommendations(client: Any, user_id: str) -> None:
    """Remove stale ``pending`` rows for ``user_id`` before inserting a new batch."""
    client.table("recommendations").delete().eq("user_id", user_id).eq(
        "status", "pending"
    ).execute()


def insert_recommendation_rows(
    client: Any,
    *,
    user_id: str,
    batch_id: str,
    rows: list[dict[str, Any]],
) -> None:
    """Bulk-insert validated recommendation payloads for ``user_id``."""
    if not rows:
        return
    payload = []
    for r in rows:
        item = {
            "user_id": user_id,
            "skill_id": r.get("skill_id"),
            "gap_rank": r.get("gap_rank"),
            "priority_tier": r["priority_tier"],
            "recommendation_text": r["recommendation_text"],
            "resource_type": r["resource_type"],
            "resource_url": r.get("resource_url"),
            "estimated_hours": r.get("estimated_hours"),
            "status": "pending",
            "batch_id": batch_id,
        }
        payload.append(item)
    client.table("recommendations").insert(payload).execute()


def generate_batch_id(user_id: str) -> str:
    """
    Build ``batch_id`` as ``{UTC-date}_{first-8-hex-of-uuid}`` for traceability.

    Example: ``2026-03-22_a1b2c3d4``.
    """
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    compact = user_id.replace("-", "")
    prefix = compact[:8] if len(compact) >= 8 else compact
    return f"{day}_{prefix}"


def process_one_user(
    *,
    client: Any,
    anthropic_client: Anthropic,
    user_id: str,
    trends_cache: list[dict[str, Any]],
    dry_run: bool,
    stats: RecommenderRunStats,
) -> None:
    """
    Load context, call Claude once, parse JSON, replace pending rows, insert.

    On invalid JSON, logs the raw response and returns without writing.
    """
    gaps = fetch_gap_analysis(client, user_id)
    if not gaps:
        LOGGER.info("User %s: no rows in mart_skill_gap_analysis; skipping.", user_id)
        stats.users_skipped_no_gaps += 1
        return

    profile = fetch_user_profile(client, user_id)
    if profile is None:
        LOGGER.warning("User %s: no user_profiles row; skipping.", user_id)
        stats.users_skipped_no_profile += 1
        return

    target_roles = fetch_target_roles(client, user_id)
    user_message = build_user_message(
        profile=profile,
        target_roles=target_roles,
        gaps=gaps,
        trends=trends_cache,
    )

    gap_lookup = build_gap_skill_lookup(gaps)
    batch_id = generate_batch_id(user_id)

    LOGGER.info("User %s: calling Claude Sonnet (batch_id=%s)", user_id, batch_id)

    if dry_run:
        LOGGER.info("=== DRY RUN: full user message ===\n%s", user_message)

    try:
        response_text = call_claude_sonnet(anthropic_client, user_message=user_message)
    except Exception as exc:  # noqa: BLE001
        stats.users_api_error += 1
        LOGGER.warning("User %s: Claude API failed after retry, skipping: %s", user_id, exc)
        return

    if dry_run:
        LOGGER.info("=== DRY RUN: raw Claude response ===\n%s", response_text)

    try:
        parsed_list = extract_json_array_from_response(response_text)
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        stats.users_json_error += 1
        LOGGER.warning(
            "User %s: invalid JSON from Claude (%s). Raw response:\n%s",
            user_id,
            exc,
            response_text,
        )
        return

    rows_out: list[dict[str, Any]] = []
    for item in parsed_list:
        if not isinstance(item, dict):
            stats.recommendations_skipped_invalid += 1
            continue
        norm = validate_recommendation_row(item, gap_lookup=gap_lookup, stats=stats)
        if norm is None:
            stats.recommendations_skipped_invalid += 1
            continue
        rows_out.append(norm)

    if not rows_out:
        LOGGER.warning("User %s: no valid recommendations after validation; nothing to write.", user_id)
        return

    if dry_run:
        LOGGER.info(
            "User %s: dry-run — would insert %d recommendation(s); not writing to DB.",
            user_id,
            len(rows_out),
        )
        stats.users_succeeded += 1
        stats.recommendations_inserted += len(rows_out)
        stats.per_user_counts[user_id] = len(rows_out)
        return

    try:
        delete_pending_recommendations(client, user_id)
        insert_recommendation_rows(client, user_id=user_id, batch_id=batch_id, rows=rows_out)
    except Exception as exc:  # noqa: BLE001
        LOGGER.exception("User %s: failed to write recommendations: %s", user_id, exc)
        return

    stats.users_succeeded += 1
    stats.recommendations_inserted += len(rows_out)
    stats.per_user_counts[user_id] = len(rows_out)
    LOGGER.info("User %s: inserted %d recommendation(s).", user_id, len(rows_out))


def run_recommender(
    *,
    user_id: str | None,
    dry_run: bool,
) -> RecommenderRunStats:
    """
    Main entry: load marts, optionally filter by ``user_id``, generate recommendations.

    Args:
        user_id: If set, only this user; otherwise ``distinct`` user_ids from gap mart.
        dry_run: Log prompts and model output; do not mutate ``recommendations``.
    """
    from datapulse.db import get_client

    client = get_client()
    api_key = get_anthropic_api_key()
    anthropic_client = Anthropic(api_key=api_key)

    trends_cache = fetch_trend_summary(client)
    LOGGER.info("Loaded %d trend row(s) for market context.", len(trends_cache))

    if user_id is not None:
        user_ids = [user_id]
    else:
        user_ids = fetch_user_ids_with_gaps(client)

    stats = RecommenderRunStats(users_considered=len(user_ids))
    LOGGER.info("Recommender run: %d user(s) to process.", len(user_ids))

    for uid in user_ids:
        try:
            process_one_user(
                client=client,
                anthropic_client=anthropic_client,
                user_id=uid,
                trends_cache=trends_cache,
                dry_run=dry_run,
                stats=stats,
            )
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception(
                "User %s: unexpected error during recommendation generation: %s", uid, exc
            )

    LOGGER.info("=== Recommender finished ===")
    LOGGER.info("Users considered: %d", stats.users_considered)
    LOGGER.info("Users succeeded: %d", stats.users_succeeded)
    LOGGER.info("Skipped (no gaps): %d", stats.users_skipped_no_gaps)
    LOGGER.info("Skipped (no profile): %d", stats.users_skipped_no_profile)
    LOGGER.info("Users with JSON parse errors: %d", stats.users_json_error)
    LOGGER.info("Users with API errors: %d", stats.users_api_error)
    LOGGER.info("Total recommendations inserted (or dry-run counted): %d", stats.recommendations_inserted)
    LOGGER.info("Recommendations skipped (invalid fields): %d", stats.recommendations_skipped_invalid)
    LOGGER.info("Unmapped skill_name warnings: %d", stats.unmapped_skill_warnings)
    LOGGER.info("Per-user counts: %s", stats.per_user_counts)

    return stats


def _configure_logging() -> None:
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="%(levelname)s %(name)s: %(message)s",
        )


def main() -> None:
    """CLI: ``python -m datapulse.recommender`` with optional user filter and dry-run."""
    parser = argparse.ArgumentParser(
        description="Generate personalized recommendations from gap marts via Claude Sonnet.",
    )
    parser.add_argument(
        "--user-id",
        type=str,
        default=None,
        metavar="UUID",
        help="Generate recommendations for a single user only.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log prompts and model output; do not write to Supabase.",
    )
    args = parser.parse_args()

    _configure_logging()

    uid = args.user_id.strip() if args.user_id else None
    if uid == "":
        raise SystemExit("--user-id must be non-empty when provided")

    run_recommender(user_id=uid, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
