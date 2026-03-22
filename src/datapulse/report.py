"""
DataPulse weekly career intelligence report: Supabase marts + profile → markdown file.

Writes ``docs/reports/YYYY-MM-DD.md`` (UTC date) or prints to stdout when ``--dry-run``.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final

from datapulse.config import SUPABASE_URL
from datapulse.db import get_client

LOGGER = logging.getLogger("datapulse.report")

_PRIORITY_ORDER: Final[tuple[str, ...]] = ("critical", "important", "nice_to_have")


def _configure_logging() -> None:
    """Configure root logging once (matches collector / recommender)."""
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="%(levelname)s %(name)s: %(message)s",
        )


def _project_root() -> Path:
    """Directory containing ``pyproject.toml`` (same resolution as ``config``)."""
    here = Path(__file__).resolve().parent
    for parent in [here, *here.parents]:
        if (parent / "pyproject.toml").is_file():
            return parent
    return here


def fetch_first_user_id_from_gap_mart(client: Any) -> str | None:
    """
    Return the first ``user_id`` from ``mart_skill_gap_analysis`` (sorted for stability).

    Returns:
        A user id string, or ``None`` if the mart has no rows.
    """
    try:
        result = client.table("mart_skill_gap_analysis").select("user_id").execute()
    except Exception as exc:
        LOGGER.exception(
            "Supabase query failed while listing users from mart_skill_gap_analysis: %s",
            exc,
        )
        raise RuntimeError(
            "Could not load user ids from mart_skill_gap_analysis. "
            "Check SUPABASE_URL/SUPABASE_KEY and network connectivity."
        ) from exc

    raw = result.data or []
    seen: set[str] = set()
    for row in raw:
        uid = row.get("user_id")
        if uid is not None:
            seen.add(str(uid))
    if not seen:
        return None
    return sorted(seen)[0]


def fetch_user_profile_report_fields(
    client: Any,
    user_id: str,
) -> dict[str, Any] | None:
    """
    Load profile fields used in the report header and snapshot.

    Returns:
        One row as a dict, or ``None`` if no profile exists.
    """
    try:
        result = (
            client.table("user_profiles")
            .select(
                "display_name, role_title, industry, country, "
                "years_total_experience, career_narrative"
            )
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
    except Exception as exc:
        LOGGER.exception(
            "Supabase query failed for user_profiles (user_id=%s): %s",
            user_id,
            exc,
        )
        raise RuntimeError(
            f"Could not load user_profiles for user_id={user_id}. "
            "Check credentials and that the row exists."
        ) from exc

    rows = result.data or []
    if not rows:
        return None
    return dict(rows[0])


def fetch_user_target_roles(
    client: Any,
    user_id: str,
) -> list[dict[str, Any]]:
    """Load target roles ordered by ``priority`` ascending."""
    try:
        result = (
            client.table("user_target_roles")
            .select("role_name, priority, timeline, market_scope")
            .eq("user_id", user_id)
            .order("priority")
            .execute()
        )
    except Exception as exc:
        LOGGER.exception(
            "Supabase query failed for user_target_roles (user_id=%s): %s",
            user_id,
            exc,
        )
        raise RuntimeError(
            f"Could not load user_target_roles for user_id={user_id}."
        ) from exc

    return list(result.data or [])


def fetch_skill_gaps_top10(
    client: Any,
    user_id: str,
) -> list[dict[str, Any]]:
    """Load up to 10 gap rows for the user, ordered by ``gap_rank`` ascending."""
    try:
        result = (
            client.table("mart_skill_gap_analysis")
            .select(
                "skill_display_name, skill_category, user_level, demand_score, "
                "gap_score, gap_rank, gap_category, priority_tier"
            )
            .eq("user_id", user_id)
            .order("gap_rank")
            .limit(15)
            .execute()
        )
    except Exception as exc:
        LOGGER.exception(
            "Supabase query failed for mart_skill_gap_analysis (user_id=%s): %s",
            user_id,
            exc,
        )
        raise RuntimeError(
            f"Could not load mart_skill_gap_analysis for user_id={user_id}."
        ) from exc

    return list(result.data or [])


def fetch_market_trends_top10(client: Any) -> list[dict[str, Any]]:
    """Load top 10 market trends by ``trending_score`` (global, no user filter)."""
    try:
        result = (
            client.table("mart_trend_summary")
            .select(
                "skill_display_name, skill_category, signal_count, "
                "avg_strength, trending_score"
            )
            .order("trending_score", desc=True)
            .limit(10)
            .execute()
        )
    except Exception as exc:
        LOGGER.exception(
            "Supabase query failed for mart_trend_summary: %s",
            exc,
        )
        raise RuntimeError(
            "Could not load mart_trend_summary. Run dbt or check the mart."
        ) from exc

    return list(result.data or [])


def fetch_pending_recommendations(
    client: Any,
    user_id: str,
) -> list[dict[str, Any]]:
    """Load pending recommendations ordered by ``gap_rank`` ascending."""
    try:
        result = (
            client.table("recommendations")
            .select(
                "skill_id, gap_rank, priority_tier, recommendation_text, "
                "resource_type, estimated_hours, batch_id"
            )
            .eq("user_id", user_id)
            .eq("status", "pending")
            .order("gap_rank")
            .execute()
        )
    except Exception as exc:
        LOGGER.exception(
            "Supabase query failed for recommendations (user_id=%s): %s",
            user_id,
            exc,
        )
        raise RuntimeError(
            f"Could not load recommendations for user_id={user_id}."
        ) from exc

    return list(result.data or [])


def _escape_table_cell(value: Any) -> str:
    """Make a value safe for a markdown pipe table cell."""
    if value is None:
        return ""
    text = str(value).replace("\n", " ").replace("|", "\\|")
    return text


def build_gap_lookups(
    gaps: list[dict[str, Any]],
) -> tuple[dict[int, str], dict[str, str]]:
    """
    Build maps for resolving recommendation rows to skill display names.

    Returns:
        ``(by_gap_rank, by_skill_id)`` — first key wins per gap row order.
    """
    by_rank: dict[int, str] = {}
    by_skill: dict[str, str] = {}
    for row in gaps:
        name = row.get("skill_display_name")
        if not isinstance(name, str) or not name.strip():
            continue
        gr = row.get("gap_rank")
        if gr is not None:
            try:
                gri = int(gr)
                by_rank.setdefault(gri, name.strip())
            except (TypeError, ValueError):
                pass
        sid = row.get("skill_id")
        if sid is not None:
            by_skill.setdefault(str(sid), name.strip())
    return by_rank, by_skill


def _gap_rank_sort_key(rec: dict[str, Any]) -> int:
    """
    Return a sort key for ordering recommendations by ``gap_rank`` ascending.

    Missing or non-numeric ``gap_rank`` values sort last.
    """
    gr = rec.get("gap_rank")
    if gr is None:
        return 10**9
    try:
        return int(gr)
    except (TypeError, ValueError):
        return 10**9


def resolve_skill_name(
    rec: dict[str, Any],
    by_gap_rank: dict[int, str],
    by_skill_id: dict[str, str],
) -> str:
    """Resolve display name for one recommendation using gap_rank first, then skill_id."""
    gr = rec.get("gap_rank")
    if gr is not None:
        try:
            gri = int(gr)
            if gri in by_gap_rank:
                return by_gap_rank[gri]
        except (TypeError, ValueError):
            pass
    sid = rec.get("skill_id")
    if sid is not None:
        key = str(sid)
        if key in by_skill_id:
            return by_skill_id[key]
    return "Unknown skill"


def render_markdown_report(
    *,
    report_date_utc: str,
    profile: dict[str, Any],
    target_roles: list[dict[str, Any]],
    gaps: list[dict[str, Any]],
    trends: list[dict[str, Any]],
    recommendations: list[dict[str, Any]],
) -> str:
    """
    Assemble the full markdown document for one user and one run.

    Args:
        report_date_utc: ``YYYY-MM-DD`` in UTC (filename and header).
        profile: Row from ``user_profiles`` (required fields).
        target_roles: Rows from ``user_target_roles``.
        gaps: Up to 10 gap rows.
        trends: Up to 10 trend rows.
        recommendations: Pending recommendation rows.
    """
    display_name = profile.get("display_name") or "n/a"
    role_title = profile.get("role_title") or "n/a"
    country = profile.get("country") or "n/a"
    industry = profile.get("industry") or "n/a"
    years = profile.get("years_total_experience")
    years_s = str(years) if years is not None else "n/a"
    narrative = profile.get("career_narrative") or ""

    lines: list[str] = [
        "# DataPulse — Weekly Career Intelligence Report",
        "",
        f"Generated: {report_date_utc}",
        f"User: {display_name} | {role_title} | {country}",
        "",
        "## Profile Snapshot",
        "",
        f"- **Current role:** {role_title}",
        f"- **Industry:** {industry}",
        f"- **Years experience (total):** {years_s}",
        "",
        "### Target roles",
        "",
    ]

    if not target_roles:
        lines.append("_No target roles specified._")
    else:
        for tr in target_roles:
            rname = tr.get("role_name") or "Unknown"
            pri = tr.get("priority")
            pri_s = str(pri) if pri is not None else "?"
            tl = tr.get("timeline") or "n/a"
            scope = tr.get("market_scope") or "n/a"
            lines.append(
                f"- **{rname}** — priority {pri_s}; timeline: {tl}; scope: {scope}"
            )

    lines.extend(["", "### Career narrative", ""])
    if narrative.strip():
        lines.append(narrative.strip())
    else:
        lines.append("_No narrative provided._")

    lines.extend(["", "## Market Trends", ""])
    if not trends:
        lines.append("_No trend data available._")
    else:
        lines.append(
            "| Skill | Category | Signals | Avg strength | Trending score |"
        )
        lines.append("| --- | --- | --- | --- | --- |")
        for row in trends:
            lines.append(
                "| "
                + " | ".join(
                    _escape_table_cell(x)
                    for x in (
                        row.get("skill_display_name"),
                        row.get("skill_category"),
                        row.get("signal_count"),
                        row.get("avg_strength"),
                        row.get("trending_score"),
                    )
                )
                + " |"
            )

    lines.extend(["", "## Top Skill Gaps", ""])
    if not gaps:
        lines.append("_No skill gaps in the mart for this user._")
    else:
        lines.append(
            "| Rank | Skill | Category | Your level | Market demand | "
            "Gap score | Priority tier |"
        )
        lines.append("| --- | --- | --- | --- | --- | --- | --- |")
        for row in gaps:
            lines.append(
                "| "
                + " | ".join(
                    _escape_table_cell(x)
                    for x in (
                        row.get("gap_rank"),
                        row.get("skill_display_name"),
                        row.get("skill_category"),
                        row.get("user_level"),
                        row.get("demand_score"),
                        row.get("gap_score"),
                        row.get("priority_tier"),
                    )
                )
                + " |"
            )

    by_rank, by_skill = build_gap_lookups(gaps)

    tier_buckets: dict[str, list[dict[str, Any]]] = {t: [] for t in _PRIORITY_ORDER}
    other: list[dict[str, Any]] = []
    for rec in recommendations:
        pt = rec.get("priority_tier")
        if isinstance(pt, str) and pt in tier_buckets:
            tier_buckets[pt].append(rec)
        else:
            other.append(rec)

    for t in _PRIORITY_ORDER:
        tier_buckets[t].sort(key=_gap_rank_sort_key)
    other.sort(key=_gap_rank_sort_key)

    lines.extend(["", "## Recommendations", ""])

    if not recommendations:
        lines.append("_No pending recommendations._")
    else:
        for tier in _PRIORITY_ORDER:
            bucket = tier_buckets[tier]
            if not bucket:
                continue
            lines.append(f"### {tier.replace('_', ' ').title()}")
            lines.append("")
            for rec in bucket:
                skill_name = resolve_skill_name(rec, by_rank, by_skill)
                pt = rec.get("priority_tier")
                pt_s = str(pt) if pt is not None else "unknown"
                est = rec.get("estimated_hours")
                est_s = f"{est}" if est is not None else "n/a"
                rtype = rec.get("resource_type") or "n/a"
                body = rec.get("recommendation_text") or ""
                lines.append(f"{pt_s}: {skill_name}")
                lines.append("")
                lines.append(
                    f"Resource type: {rtype} | Estimated time: {est_s}h"
                )
                lines.append("")
                lines.append(body.strip())
                lines.append("")
        if other:
            lines.append("### Other")
            lines.append("")
            for rec in other:
                skill_name = resolve_skill_name(rec, by_rank, by_skill)
                pt = rec.get("priority_tier")
                pt_s = str(pt) if pt is not None else "unknown"
                est = rec.get("estimated_hours")
                est_s = f"{est}" if est is not None else "n/a"
                rtype = rec.get("resource_type") or "n/a"
                body = rec.get("recommendation_text") or ""
                lines.append(f"{pt_s}: {skill_name}")
                lines.append("")
                lines.append(
                    f"Resource type: {rtype} | Estimated time: {est_s}h"
                )
                lines.append("")
                lines.append(body.strip())
                lines.append("")

    lines.extend(
        [
            "---",
            "",
            "Report generated by DataPulse. Approve or reject recommendations "
            "with datapulse approve/reject <id>.",
            "",
        ]
    )

    return "\n".join(lines).rstrip() + "\n"


def run_report(*, user_id: str | None, dry_run: bool) -> str:
    """
    Load data from Supabase and write or print the markdown report.

    Args:
        user_id: User to report on, or ``None`` to use the first id from the gap mart.
        dry_run: If True, print markdown to stdout and do not write a file.

    Returns:
        The markdown string that was written or printed.

    Raises:
        RuntimeError: If the Supabase client cannot be created or required data is missing.
        SystemExit: If no default user exists when ``user_id`` is omitted.
    """
    LOGGER.debug("Supabase URL configured: %s", bool(SUPABASE_URL))
    try:
        client = get_client()
    except Exception as exc:
        LOGGER.exception("Failed to initialize Supabase client: %s", exc)
        raise RuntimeError(
            "Could not connect to Supabase. Verify SUPABASE_URL and SUPABASE_KEY in .env."
        ) from exc

    uid = user_id
    if uid is None:
        default_id = fetch_first_user_id_from_gap_mart(client)
        if default_id is None:
            LOGGER.error(
                "No user_id provided and mart_skill_gap_analysis has no rows."
            )
            raise SystemExit(1)
        uid = default_id
        LOGGER.info("Using default user_id from gap mart: %s", uid)

    profile = fetch_user_profile_report_fields(client, uid)
    if profile is None:
        LOGGER.error("No user_profiles row for user_id=%s; aborting.", uid)
        raise SystemExit(1)

    target_roles = fetch_user_target_roles(client, uid)
    gaps = fetch_skill_gaps_top10(client, uid)
    trends = fetch_market_trends_top10(client)
    recommendations = fetch_pending_recommendations(client, uid)

    now = datetime.now(timezone.utc)
    report_date = now.strftime("%Y-%m-%d")

    md = render_markdown_report(
        report_date_utc=report_date,
        profile=profile,
        target_roles=target_roles,
        gaps=gaps,
        trends=trends,
        recommendations=recommendations,
    )

    if dry_run:
        sys.stdout.write(md)
        if not md.endswith("\n"):
            sys.stdout.write("\n")
        LOGGER.info("Dry-run: markdown printed to stdout (%d bytes).", len(md.encode("utf-8")))
        return md

    out_dir = _project_root() / "docs" / "reports"
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        LOGGER.exception("Could not create report directory %s: %s", out_dir, exc)
        raise RuntimeError(f"Failed to create directory {out_dir}") from exc

    out_path = out_dir / f"{report_date}.md"
    try:
        out_path.write_text(md, encoding="utf-8")
    except OSError as exc:
        LOGGER.exception("Failed to write report file %s: %s", out_path, exc)
        raise RuntimeError(f"Failed to write {out_path}") from exc

    LOGGER.info("Wrote report: %s", out_path)
    return md


def main() -> None:
    """CLI: ``python -m datapulse.report`` with optional ``--user-id`` and ``--dry-run``."""
    parser = argparse.ArgumentParser(
        description="Generate weekly career intelligence markdown report (Supabase → docs/reports).",
    )
    parser.add_argument(
        "--user-id",
        type=str,
        default=None,
        metavar="UUID",
        help="Report for this user. Default: first user_id in mart_skill_gap_analysis.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print markdown to stdout instead of writing docs/reports/YYYY-MM-DD.md.",
    )
    args = parser.parse_args()

    _configure_logging()

    uid = args.user_id.strip() if args.user_id else None
    if uid == "":
        raise SystemExit("--user-id must be non-empty when provided")

    try:
        run_report(user_id=uid, dry_run=args.dry_run)
    except RuntimeError as exc:
        LOGGER.error("%s", exc)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
