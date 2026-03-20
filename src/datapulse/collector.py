"""
RSS ingestion for DataPulse: fetch configured feeds, normalize entries, upsert into
``feed_items`` (PostgreSQL on Supabase). Relevance filtering applies only to noisy
community sources (Reddit, Hacker News); all other feeds insert every entry.
"""

from __future__ import annotations

import argparse
import calendar
import logging
import re
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any, Final

import feedparser

from datapulse.feeds_config import FEEDS, FeedConfig

# Fixed name so logs read ``datapulse.collector`` when the module is run as ``__main__``.
LOGGER = logging.getLogger("datapulse.collector")

_USER_AGENT: Final[str] = "DataPulse/0.1 (RSS collector; +https://github.com/datapulse)"
_FETCH_TIMEOUT_SEC: Final[float] = 30.0
_UPSERT_CHUNK_SIZE: Final[int] = 300

_NOISY_SOURCE_TITLE_KEYWORDS: Final[tuple[str, ...]] = (
    "data",
    "analytics",
    "engineering",
    "dbt",
    "sql",
    "python",
    "pipeline",
    "etl",
    "warehouse",
    "lakehouse",
    "snowflake",
    "databricks",
    "spark",
    "airflow",
    "dagster",
    "prefect",
    "fivetran",
    "airbyte",
    "postgres",
    "supabase",
    "bigquery",
    "redshift",
    "tableau",
    "power bi",
    "looker",
    "machine learning",
    "ml",
    "ai",
    "llm",
    "claude",
    "gpt",
    "openai",
    "anthropic",
    "vector",
    "rag",
    "cloud",
    "aws",
    "gcp",
    "azure",
    "docker",
    "kubernetes",
    "terraform",
    "ci/cd",
    "github actions",
    "duckdb",
    "polars",
    "pandas",
    "kafka",
    "streaming",
    "governance",
    "data quality",
    "data contract",
    "data mesh",
    "data catalog",
    "metadata",
    "lineage",
    "observability",
    "monitor",
)


@dataclass
class FeedRunResult:
    """Per-feed counters and optional error for the summary report."""

    key: str
    name: str
    entries_in_feed: int = 0
    skipped_by_filter: int = 0
    candidates: int = 0
    new_inserted: int = 0
    duplicates_skipped: int = 0
    error: str | None = None


@dataclass
class CollectorTotals:
    """Aggregates across the full run."""

    feeds_attempted: int = 0
    feeds_succeeded: int = 0
    total_new: int = 0
    total_duplicates: int = 0
    total_filtered: int = 0
    dry_run_rows_ready: int = 0
    failed: list[tuple[str, str]] = field(default_factory=list)


class _HTMLTextExtractor(HTMLParser):
    """Collect visible text nodes; used to strip tags from RSS summaries."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._chunks: list[str] = []

    def handle_data(self, data: str) -> None:
        self._chunks.append(data)

    def get_text(self) -> str:
        return "".join(self._chunks)


def _collapse_ws(value: str) -> str:
    """Normalize internal whitespace after tag stripping."""
    return re.sub(r"\s+", " ", value).strip()


def strip_html(raw: str | None) -> str:
    """
    Remove HTML tags from a string using the stdlib parser (no extra dependency).

    Many RSS ``description`` fields contain markup; we store plain text for downstream use.
    """
    if not raw:
        return ""
    parser = _HTMLTextExtractor()
    try:
        parser.feed(raw)
        parser.close()
    except Exception:  # noqa: BLE001
        LOGGER.debug("HTML strip failed; falling back to tag-stripping regex", exc_info=True)
        return _collapse_ws(re.sub(r"<[^>]+>", " ", raw))
    return _collapse_ws(parser.get_text())


def is_noisy_community_feed(source_key: str) -> bool:
    """
    Return True if this source should use keyword pre-filtering (Reddit, HN).

    Spec: ``source_key`` contains ``reddit`` or ``hacker_news``.
    """
    key_l = source_key.lower()
    return "reddit" in key_l or "hacker_news" in key_l


def title_passes_noisy_filter(title: str) -> bool:
    """Return True if ``title`` contains at least one relevance keyword."""
    tl = title.lower()
    return any(kw in tl for kw in _NOISY_SOURCE_TITLE_KEYWORDS)


def time_struct_to_iso8601_tz(struct_time: Any) -> str | None:
    """
    Convert feedparser's ``published_parsed`` / ``updated_parsed`` to ISO 8601.

    Feed dates use UTC struct tuples; ``calendar.timegm`` matches that convention.
    """
    if struct_time is None:
        return None
    try:
        ts = calendar.timegm(struct_time)
    except (TypeError, ValueError, OverflowError):
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def extract_published_iso(entry: Any) -> str | None:
    """Pick the best available parsed timestamp from an RSS/Atom entry."""
    for key in ("published_parsed", "updated_parsed"):
        parsed = entry.get(key)
        if parsed:
            iso = time_struct_to_iso8601_tz(parsed)
            if iso:
                return iso
    return None


def extract_author(entry: Any) -> str | None:
    """Normalize author from RSS ``author`` or Atom ``authors`` list."""
    author = entry.get("author")
    if author:
        s = str(author).strip()
        return s or None
    authors = entry.get("authors")
    if isinstance(authors, list) and authors:
        names: list[str] = []
        for item in authors:
            if isinstance(item, dict):
                n = item.get("name")
                if n:
                    names.append(str(n).strip())
        if names:
            return ", ".join(names)
    return None


def extract_entry_url(entry: Any) -> str | None:
    """Resolve canonical article URL (``link`` preferred, else ``id`` if HTTP(S))."""
    link = entry.get("link")
    if link:
        s = str(link).strip()
        if s:
            return s
    eid = entry.get("id")
    if eid:
        sid = str(eid).strip()
        if sid.startswith(("http://", "https://")):
            return sid
    return None


def fetch_feed_bytes(url: str, timeout: float = _FETCH_TIMEOUT_SEC) -> bytes:
    """
    Download raw RSS/Atom bytes with timeout and a real browser-like User-Agent.

    ``feedparser.parse(url)`` does not expose per-request timeouts; urllib does.
    """
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def parse_feed_document(content: bytes, feed_meta: FeedConfig) -> feedparser.FeedParserDict:
    """Parse bytes with feedparser; log bozo / structural issues without aborting."""
    parsed: feedparser.FeedParserDict = feedparser.parse(content)
    if getattr(parsed, "bozo", False) and getattr(parsed, "bozo_exception", None):
        LOGGER.warning(
            "Feed %s (%s): parse reported warnings: %s",
            feed_meta["key"],
            feed_meta["name"],
            parsed.bozo_exception,
        )
    return parsed


def entry_to_row(entry: Any, feed_meta: FeedConfig, fetched_at_iso: str) -> dict[str, Any] | None:
    """
    Map one feedparser entry to a ``feed_items`` payload.

    Returns ``None`` when the row is not insertable (missing canonical URL).
    """
    url = extract_entry_url(entry)
    if not url:
        return None

    title_raw = entry.get("title")
    title = str(title_raw).strip() if title_raw else ""
    if not title:
        title = "(untitled)"

    raw_summary = entry.get("summary") or entry.get("description") or ""
    summary_text = strip_html(str(raw_summary)) if raw_summary else ""

    row: dict[str, Any] = {
        "source_key": feed_meta["key"],
        "source_category": feed_meta["category"],
        "url": url,
        "title": title,
        "summary": summary_text or None,
        "author": extract_author(entry),
        "published_at": extract_published_iso(entry),
        "fetched_at": fetched_at_iso,
        "language": feed_meta["language"],
        "is_processed": False,
    }
    return row


def filter_entries_for_feed(
    entries: list[Any],
    feed_meta: FeedConfig,
) -> tuple[list[Any], int]:
    """
    Apply Reddit/HN title keyword gate; other feeds pass all entries through.

    Returns ``(entries_to_process, skipped_count)``.
    """
    if not is_noisy_community_feed(feed_meta["key"]):
        return list(entries), 0

    kept: list[Any] = []
    skipped = 0
    for entry in entries:
        title_raw = entry.get("title")
        title = str(title_raw) if title_raw else ""
        if title_passes_noisy_filter(title):
            kept.append(entry)
        else:
            skipped += 1
    return kept, skipped


def upsert_feed_item_batch(
    client: Any,
    rows: list[dict[str, Any]],
) -> tuple[int, int]:
    """
    Upsert rows with ``ON CONFLICT (url) DO NOTHING`` via Supabase.

    Returns ``(inserted_count, duplicate_ignored_count)`` based on the API
    response length (PostgREST omits unchanged rows when ignoring duplicates).
    """
    if not rows:
        return 0, 0

    inserted = 0
    ignored = 0
    for i in range(0, len(rows), _UPSERT_CHUNK_SIZE):
        chunk = rows[i : i + _UPSERT_CHUNK_SIZE]
        result = (
            client.table("feed_items")
            .upsert(chunk, on_conflict="url", ignore_duplicates=True)
            .execute()
        )
        data = result.data
        chunk_new = len(data) if data else 0
        inserted += chunk_new
        ignored += len(chunk) - chunk_new

    return inserted, ignored


def collect_feeds(*, dry_run: bool = False) -> CollectorTotals:
    """
    Fetch every configured feed, normalize entries, and upsert (unless ``dry_run``).

    Args:
        dry_run: When True, skip Supabase writes and log rows that would be sent.

    Returns:
        Aggregated counters plus ``failed`` feed keys with error messages.
    """
    totals = CollectorTotals()
    fetched_at_iso = datetime.now(timezone.utc).isoformat()

    client: Any | None = None
    if not dry_run:
        from datapulse.db import get_client

        client = get_client()

    for feed_meta in FEEDS:
        totals.feeds_attempted += 1
        result = FeedRunResult(key=feed_meta["key"], name=feed_meta["name"])

        try:
            body = fetch_feed_bytes(feed_meta["url"])
            parsed = parse_feed_document(body, feed_meta)
            entries = list(parsed.entries)
            result.entries_in_feed = len(entries)

            if result.entries_in_feed == 0:
                LOGGER.warning(
                    "Feed %s (%s): 0 entries returned — check URL or availability",
                    feed_meta["key"],
                    feed_meta["name"],
                )

            to_process, filtered = filter_entries_for_feed(entries, feed_meta)
            result.skipped_by_filter = filtered
            totals.total_filtered += filtered
            after_filter = len(to_process)

            rows: list[dict[str, Any]] = []
            for entry in to_process:
                row = entry_to_row(entry, feed_meta, fetched_at_iso)
                if row is not None:
                    rows.append(row)

            result.candidates = len(rows)

            if dry_run:
                totals.dry_run_rows_ready += result.candidates
                LOGGER.info(
                    "[dry-run] %s (%s): %d entries in feed, %d after keyword filter, "
                    "%d row(s) ready to upsert",
                    feed_meta["key"],
                    feed_meta["name"],
                    result.entries_in_feed,
                    after_filter,
                    result.candidates,
                )
                if rows:
                    sample = rows[0]
                    LOGGER.info(
                        "[dry-run] sample row: title=%r url=%r",
                        sample.get("title"),
                        sample.get("url"),
                    )
            else:
                assert client is not None
                new_count, dup_count = upsert_feed_item_batch(client, rows)
                result.new_inserted = new_count
                result.duplicates_skipped = dup_count
                totals.total_new += new_count
                totals.total_duplicates += dup_count

                LOGGER.info(
                    "%s (%s): inserted %d, duplicates skipped %d (from %d candidates)",
                    feed_meta["key"],
                    feed_meta["name"],
                    new_count,
                    dup_count,
                    result.candidates,
                )

            totals.feeds_succeeded += 1

        except urllib.error.HTTPError as exc:
            msg = f"HTTP {exc.code}: {exc.reason}"
            LOGGER.warning("Feed %s failed: %s", feed_meta["key"], msg)
            result.error = msg
            totals.failed.append((feed_meta["key"], msg))

        except urllib.error.URLError as exc:
            msg = str(exc.reason) if exc.reason else str(exc)
            LOGGER.warning("Feed %s failed (URL error): %s", feed_meta["key"], msg)
            result.error = msg
            totals.failed.append((feed_meta["key"], msg))

        except socket.timeout as exc:
            msg = str(exc) or "request timed out"
            LOGGER.warning("Feed %s timed out: %s", feed_meta["key"], msg)
            result.error = msg
            totals.failed.append((feed_meta["key"], msg))

        except TimeoutError as exc:
            msg = str(exc) or "request timed out"
            LOGGER.warning("Feed %s timed out: %s", feed_meta["key"], msg)
            result.error = msg
            totals.failed.append((feed_meta["key"], msg))

        except Exception as exc:  # noqa: BLE001
            msg = f"{type(exc).__name__}: {exc}"
            LOGGER.warning("Feed %s failed: %s", feed_meta["key"], msg, exc_info=True)
            result.error = msg
            totals.failed.append((feed_meta["key"], msg))

    _log_run_summary(totals, dry_run=dry_run)
    return totals


def _log_run_summary(totals: CollectorTotals, *, dry_run: bool) -> None:
    """Emit final human-readable totals (logging, not stdout-only prints)."""
    LOGGER.info(
        "=== Collector finished (%s) ===",
        "dry-run" if dry_run else "write",
    )
    LOGGER.info("Feeds attempted: %d; succeeded: %d", totals.feeds_attempted, totals.feeds_succeeded)
    if dry_run:
        LOGGER.info("No database writes (dry-run).")
        LOGGER.info("Total row(s) that would be upserted: %d", totals.dry_run_rows_ready)
    else:
        LOGGER.info("New rows inserted: %d", totals.total_new)
        LOGGER.info("Duplicates skipped (existing URL): %d", totals.total_duplicates)
    LOGGER.info("Entries filtered (Reddit/HN keywords): %d", totals.total_filtered)

    if totals.failed:
        LOGGER.info("Failed feeds (%d):", len(totals.failed))
        for key, err in totals.failed:
            LOGGER.info("  - %s: %s", key, err)
    else:
        LOGGER.info("No feed-level failures.")


def _configure_logging() -> None:
    """INFO to stderr by default; idempotent if handlers already exist."""
    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="%(levelname)s %(name)s: %(message)s",
        )


def main() -> None:
    """CLI entry: optional ``--dry-run`` without touching Supabase."""
    parser = argparse.ArgumentParser(description="DataPulse RSS collector (feed_items ingestion).")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and parse feeds only; log what would be upserted.",
    )
    args = parser.parse_args()
    _configure_logging()
    collect_feeds(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
