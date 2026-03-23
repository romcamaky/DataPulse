"""
Market signal extraction: unprocessed ``feed_items`` → Claude Haiku → ``market_signals``.

Runs as a batch pipeline with skill mapping to the canonical ``skills`` taxonomy and
optional ``skill_id`` when a match is found.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Final

from anthropic import Anthropic
from anthropic import APIError, APIConnectionError, RateLimitError

from datapulse.config import get_anthropic_api_key
from datapulse.skill_aliases import SKILL_ALIASES

LOGGER = logging.getLogger("datapulse.extractor")

# Model and generation limits (Haiku is cost-efficient for high-volume batch labeling).
_CLAUDE_MODEL: Final[str] = "claude-haiku-4-5-20251001"
_MAX_TOKENS: Final[int] = 8192

# Default batching and rate limiting (Anthropic tier limits are generous; stay conservative).
_DEFAULT_BATCH_SIZE: Final[int] = 10
_SLEEP_BETWEEN_BATCHES_SEC: Final[float] = 1.0
_RETRY_BACKOFF_SEC: Final[float] = 5.0

_ALLOWED_SIGNAL_TYPES: Final[frozenset[str]] = frozenset(
    {
        "skill_demand",
        "tool_adoption",
        "trend_emerging",
        "trend_declining",
        "regulatory_update",
    }
)
_ALLOWED_REGIONS: Final[frozenset[str]] = frozenset({"global", "us", "eu", "cz"})

_SYSTEM_PROMPT: Final[str] = """You are a market intelligence analyst for data engineering and analytics careers.
You analyze articles and extract structured signals about technology trends, skill demands, and industry shifts.

For each article, extract 0-5 signals. Each signal represents one technology, skill, or trend mentioned in the article.

Return ONLY a JSON array, no other text. Each element:
{
  "article_index": 0,
  "skill_name_raw": "dbt",
  "signal_type": "tool_adoption",
  "strength": 4,
  "confidence": 5,
  "region": "global",
  "summary": "dbt adoption growing among mid-market companies for analytics engineering"
}

Rules:
- article_index: 0-based index matching the input article order
- skill_name_raw: the technology, tool, framework, or skill name as mentioned. Use common canonical names (e.g., "Python" not "python3", "PostgreSQL" not "postgres")
- For specific AI products (ChatGPT, Claude, GPT-4, Gemini, etc.), return the product name as-is
- For broad AI concepts, use these canonical names: "machine learning", "deep learning", "generative ai", "ai agents", "reinforcement learning", "natural language processing", "computer vision"
- For data engineering concepts, use: "data engineering", "analytics engineering", "data governance", "data observability", "data mesh"
- Prefer short, commonly used names over verbose descriptions
- signal_type: one of "skill_demand" (jobs/hiring), "tool_adoption" (usage growing), "trend_emerging" (new technology/approach), "trend_declining" (being replaced), "regulatory_update" (laws/regulations affecting data work)
- strength: 1 (briefly mentioned) to 5 (main topic of article)
- confidence: 1 (vague/uncertain interpretation) to 5 (explicitly stated)
- region: "global", "us", "eu", or "cz"
- summary: 1-2 sentences explaining the signal

If an article has no relevant signals for data/analytics careers, return an empty array for that article (omit it from the output).
Do not extract signals from articles about general news, sports, entertainment, or topics unrelated to data engineering, analytics, AI, or tech careers.
"""


@dataclass
class SkillIndex:
    """In-memory lookups built from ``skills`` rows."""

    by_name: dict[str, str]  # skills.name (lower) -> id
    by_display_lower: dict[str, str]  # normalized display_name -> id
    records: list[dict[str, Any]]


@dataclass
class ExtractionRunStats:
    """Aggregates for final logging."""

    articles_processed: int = 0
    signals_inserted: int = 0
    signals_skipped_invalid: int = 0
    batches_total: int = 0
    batches_json_error: int = 0
    batches_api_error: int = 0
    unmapped_skill_names: set[str] = field(default_factory=set)


def _normalize_display_key(display: str) -> str:
    """Lowercase and collapse whitespace for display-name equality checks."""
    return re.sub(r"\s+", " ", display.strip().lower())


def load_skill_index(rows: list[dict[str, Any]]) -> SkillIndex:
    """
    Build exact and display-name maps from Supabase ``skills`` rows.

    Each row must include ``id``, ``name``, and ``display_name``.
    """
    by_name: dict[str, str] = {}
    by_display_lower: dict[str, str] = {}
    for row in rows:
        sid = str(row["id"])
        name = str(row["name"]).strip().lower()
        display = str(row.get("display_name") or "")
        by_name[name] = sid
        dk = _normalize_display_key(display)
        if dk:
            by_display_lower[dk] = sid
    return SkillIndex(by_name=by_name, by_display_lower=by_display_lower, records=rows)


def resolve_skill_id(skill_name_raw: str, index: SkillIndex) -> str | None:
    """
    Map Claude's ``skill_name_raw`` to a canonical ``skills.id`` if possible.

    Order: exact ``name``, case-insensitive ``display_name``, then alias table → ``name``.
    """
    raw = skill_name_raw.strip()
    if not raw:
        return None

    lower = raw.lower()
    if lower in index.by_name:
        return index.by_name[lower]

    norm_display = _normalize_display_key(raw)
    if norm_display in index.by_display_lower:
        return index.by_display_lower[norm_display]

    alias_key = re.sub(r"\s+", " ", lower)
    if alias_key in SKILL_ALIASES:
        target_name = SKILL_ALIASES[alias_key]
        return index.by_name.get(target_name)

    # Single-token shortcuts (e.g. "Postgres" → postgres alias already handled).
    compact = re.sub(r"[^a-z0-9]+", "_", lower).strip("_")
    if compact in index.by_name:
        return index.by_name[compact]

    return None


def fetch_all_skills(client: Any) -> list[dict[str, Any]]:
    """Load every row from ``skills`` for mapping (small catalog ~51 rows)."""
    result = client.table("skills").select("id, name, display_name").execute()
    data = result.data or []
    return list(data)


def fetch_unprocessed_feed_items(
    client: Any,
    *,
    limit: int | None,
) -> list[dict[str, Any]]:
    """
    Return ``feed_items`` with ``is_processed = false``, newest first.

    Uses pagination because PostgREST may cap page size below the full backlog.
    """
    if limit is not None and limit <= 0:
        return []

    page_size = 1000
    collected: list[dict[str, Any]] = []
    offset = 0

    while True:
        query = (
            client.table("feed_items")
            .select("id, title, summary, source_key, language, published_at")
            .eq("is_processed", False)
            .order("published_at", desc=True)
            .range(offset, offset + page_size - 1)
        )
        result = query.execute()
        batch = result.data or []
        if not batch:
            break
        collected.extend(batch)
        if limit is not None and len(collected) >= limit:
            collected = collected[:limit]
            break
        if len(batch) < page_size:
            break
        offset += page_size

    return collected


def build_user_message(articles: list[dict[str, Any]]) -> str:
    """Format the batch user prompt: Article 0..N-1 with title, source, summary, language."""
    parts: list[str] = [
        "Analyze these articles and extract career intelligence signals.",
        "",
    ]
    for i, art in enumerate(articles):
        title = art.get("title") or ""
        src = art.get("source_key") or ""
        summary = art.get("summary") or "No summary available"
        lang = art.get("language") or "en"
        parts.append(f"Article {i}:")
        parts.append(f"Title: {title}")
        parts.append(f"Source: {src}")
        parts.append(f"Summary: {summary}")
        parts.append(f"Language: {lang}")
        parts.append("")
    return "\n".join(parts).strip()


def extract_json_array_from_response(text: str) -> list[Any]:
    """
    Parse Claude's reply into a JSON array.

    Strips optional ``` / ```json fences; on failure, tries the outermost [...] slice.
    """
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("[")
        end = cleaned.rfind("]")
        if start < 0 or end <= start:
            raise
        parsed = json.loads(cleaned[start : end + 1])

    if not isinstance(parsed, list):
        raise ValueError("Claude JSON root must be an array")
    return parsed


def validate_and_normalize_signal(raw: dict[str, Any]) -> dict[str, Any] | None:
    """
    Validate one signal object; return a normalized dict or None to skip.

    Coerces numeric types when safe; rejects out-of-range enums.
    """
    try:
        idx = raw["article_index"]
        if not isinstance(idx, int):
            idx = int(idx)
    except (KeyError, TypeError, ValueError):
        LOGGER.warning("Skipped signal: invalid article_index in %s", raw)
        return None

    skill_raw = raw.get("skill_name_raw")
    if not isinstance(skill_raw, str) or not skill_raw.strip():
        LOGGER.warning("Skipped signal: missing skill_name_raw at article_index=%s", idx)
        return None

    st = raw.get("signal_type")
    if not isinstance(st, str) or st not in _ALLOWED_SIGNAL_TYPES:
        LOGGER.warning("Skipped signal: invalid signal_type %r at article_index=%s", st, idx)
        return None

    try:
        strength = int(raw["strength"])
        confidence = int(raw["confidence"])
    except (KeyError, TypeError, ValueError):
        LOGGER.warning("Skipped signal: invalid strength/confidence at article_index=%s", idx)
        return None
    if strength < 1 or strength > 5 or confidence < 1 or confidence > 5:
        LOGGER.warning(
            "Skipped signal: strength/confidence out of range at article_index=%s", idx
        )
        return None

    region = raw.get("region", "global")
    if not isinstance(region, str):
        region = "global"
    region = region.strip().lower()
    if region not in _ALLOWED_REGIONS:
        LOGGER.warning(
            "Signal region %r invalid; defaulting to global (article_index=%s)", region, idx
        )
        region = "global"

    summary = raw.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        LOGGER.warning("Skipped signal: missing summary at article_index=%s", idx)
        return None

    return {
        "article_index": idx,
        "skill_name_raw": skill_raw.strip(),
        "signal_type": st,
        "strength": strength,
        "confidence": confidence,
        "region": region,
        "summary": summary.strip(),
    }


def call_claude_batch(
    client: Anthropic,
    *,
    user_message: str,
) -> str:
    """
    Invoke Claude with one retry after ``_RETRY_BACKOFF_SEC`` on transient errors.

    Raises on final failure so the caller can count API errors and skip the batch.
    """
    for attempt in range(2):
        try:
            msg = client.messages.create(
                model=_CLAUDE_MODEL,
                max_tokens=_MAX_TOKENS,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )
            blocks = msg.content
            if not blocks:
                raise RuntimeError("Empty response content from Claude")
            # Anthropic returns a list of content blocks; concatenate text blocks.
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


def process_batch(
    *,
    anthropic_client: Anthropic,
    supabase_client: Any | None,
    skill_index: SkillIndex,
    articles: list[dict[str, Any]],
    batch_num: int,
    batches_total: int,
    dry_run: bool,
    stats: ExtractionRunStats,
) -> None:
    """
    Run one batch: Claude → parse → map skills → insert signals → mark items processed.

    On invalid JSON, logs and returns without marking items processed.
    """
    ids_in_order = [str(a["id"]) for a in articles]
    user_message = build_user_message(articles)

    LOGGER.info(
        "Batch %d/%d: processing articles (indices 0-%d in batch)",
        batch_num,
        batches_total,
        len(articles) - 1,
    )

    try:
        response_text = call_claude_batch(anthropic_client, user_message=user_message)
    except Exception as exc:  # noqa: BLE001
        stats.batches_api_error += 1
        LOGGER.warning("Batch %d: Claude API failed after retry, skipping batch: %s", batch_num, exc)
        return

    try:
        parsed_list = extract_json_array_from_response(response_text)
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        stats.batches_json_error += 1
        LOGGER.warning(
            "Batch %d: invalid JSON from Claude (%s). Raw (truncated): %.2000s",
            batch_num,
            exc,
            response_text,
        )
        return

    rows_to_insert: list[dict[str, Any]] = []
    skipped_before = stats.signals_skipped_invalid
    for item in parsed_list:
        if not isinstance(item, dict):
            stats.signals_skipped_invalid += 1
            continue
        norm = validate_and_normalize_signal(item)
        if norm is None:
            stats.signals_skipped_invalid += 1
            continue

        art_idx = norm["article_index"]
        if art_idx < 0 or art_idx >= len(articles):
            LOGGER.warning(
                "Skipped signal: article_index %d out of range for batch size %d",
                art_idx,
                len(articles),
            )
            stats.signals_skipped_invalid += 1
            continue

        feed_item_id = ids_in_order[art_idx]
        skill_name_raw = norm["skill_name_raw"]
        skill_id = resolve_skill_id(skill_name_raw, skill_index)
        if skill_id is None:
            stats.unmapped_skill_names.add(skill_name_raw)

        row = {
            "feed_item_id": feed_item_id,
            "skill_id": skill_id,
            "skill_name_raw": skill_name_raw,
            "signal_type": norm["signal_type"],
            "strength": norm["strength"],
            "confidence": norm["confidence"],
            "region": norm["region"],
            "summary": norm["summary"],
        }
        rows_to_insert.append(row)

    skipped_in_batch = stats.signals_skipped_invalid - skipped_before
    LOGGER.info(
        "Batch %d: extracted %d valid signal(s), skipped %d invalid in this batch",
        batch_num,
        len(rows_to_insert),
        skipped_in_batch,
    )

    if dry_run:
        stats.articles_processed += len(articles)
        stats.signals_inserted += len(rows_to_insert)
        for row in rows_to_insert[:20]:
            LOGGER.info(
                "[dry-run] would insert: feed_item_id=%s skill_id=%s raw=%r type=%s",
                row["feed_item_id"],
                row["skill_id"],
                row["skill_name_raw"],
                row["signal_type"],
            )
        if len(rows_to_insert) > 20:
            LOGGER.info("[dry-run] ... and %d more row(s)", len(rows_to_insert) - 20)
        return

    assert supabase_client is not None

    if rows_to_insert:
        supabase_client.table("market_signals").insert(rows_to_insert).execute()

    supabase_client.table("feed_items").update({"is_processed": True}).in_(
        "id", ids_in_order
    ).execute()

    stats.articles_processed += len(articles)
    stats.signals_inserted += len(rows_to_insert)


def run_extractor(
    *,
    limit: int | None,
    batch_size: int,
    dry_run: bool,
) -> ExtractionRunStats:
    """
    Main pipeline: load data, batch to Claude, write ``market_signals``, flip flags.

    Args:
        limit: Max unprocessed articles to pull (newest first); ``None`` = all.
        batch_size: Articles per Claude request.
        dry_run: Call Claude but do not write to Supabase.
    """
    from datapulse.db import get_client

    supabase_client = get_client()

    skills_rows = fetch_all_skills(supabase_client)
    skill_index = load_skill_index(skills_rows)
    LOGGER.info("Loaded %d canonical skills for mapping", len(skills_rows))

    articles = fetch_unprocessed_feed_items(supabase_client, limit=limit)
    LOGGER.info("Fetched %d unprocessed feed item(s)", len(articles))

    if not articles:
        LOGGER.info("Nothing to process.")
        return ExtractionRunStats()

    api_key = get_anthropic_api_key()
    anthropic_client = Anthropic(api_key=api_key)

    batches: list[list[dict[str, Any]]] = [
        articles[i : i + batch_size] for i in range(0, len(articles), batch_size)
    ]
    batches_total = len(batches)
    stats = ExtractionRunStats(batches_total=batches_total)

    for i, batch in enumerate(batches, start=1):
        process_batch(
            anthropic_client=anthropic_client,
            supabase_client=supabase_client if not dry_run else None,
            skill_index=skill_index,
            articles=batch,
            batch_num=i,
            batches_total=batches_total,
            dry_run=dry_run,
            stats=stats,
        )
        if i < batches_total:
            time.sleep(_SLEEP_BETWEEN_BATCHES_SEC)

    LOGGER.info("=== Extraction finished ===")
    LOGGER.info("Total articles processed: %d", stats.articles_processed)
    LOGGER.info("Total signals written (or dry-run counted): %d", stats.signals_inserted)
    LOGGER.info("Signals skipped (invalid fields): %d", stats.signals_skipped_invalid)
    LOGGER.info("Batches with JSON parse errors: %d", stats.batches_json_error)
    LOGGER.info("Batches with API errors (after retry): %d", stats.batches_api_error)
    LOGGER.info(
        "Unique unmapped skill_name_raw values: %d — %s",
        len(stats.unmapped_skill_names),
        sorted(stats.unmapped_skill_names) if stats.unmapped_skill_names else "none",
    )

    return stats


def _configure_logging() -> None:
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="%(levelname)s %(name)s: %(message)s",
        )


def main() -> None:
    """CLI: ``python -m datapulse.extractor`` with optional limits and dry-run."""
    parser = argparse.ArgumentParser(
        description="Extract market_signals from feed_items via Claude Haiku.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="Process at most N unprocessed articles (newest first).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=_DEFAULT_BATCH_SIZE,
        metavar="N",
        help=f"Articles per Claude request (default {_DEFAULT_BATCH_SIZE}).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Call Claude and log results; do not write to Supabase.",
    )
    args = parser.parse_args()

    if args.batch_size < 1:
        raise SystemExit("--batch-size must be >= 1")

    _configure_logging()
    run_extractor(limit=args.limit, batch_size=args.batch_size, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
