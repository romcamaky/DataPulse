"""DataPulse command-line interface for recommendations and status checks."""

from __future__ import annotations

import argparse
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from datapulse.db import get_client

ALLOWED_RECOMMEND_STATUSES = {"pending", "approved", "rejected", "all"}
REVIEWABLE_STATUSES = {"approved", "rejected"}


def _project_root() -> Path:
    """Return project root by locating ``pyproject.toml``.

    Returns:
        Absolute path to the project root.
    """
    here = Path(__file__).resolve().parent
    for parent in [here, *here.parents]:
        if (parent / "pyproject.toml").is_file():
            return parent
    return here


def _format_hours(hours: Any) -> str:
    """Format estimated hours for terminal output.

    Args:
        hours: Raw value from Supabase row.

    Returns:
        Human-friendly string (for example, ``"8 hours"`` or ``"n/a"``).
    """
    if hours is None:
        return "n/a"
    try:
        num = int(hours)
    except (TypeError, ValueError):
        return "n/a"
    return f"{num} hour" if num == 1 else f"{num} hours"


def _parse_iso_timestamp(value: str | None) -> datetime | None:
    """Parse common ISO timestamp formats from Supabase.

    Args:
        value: ISO-like timestamp string or ``None``.

    Returns:
        Parsed ``datetime`` in UTC, or ``None`` when parsing fails.
    """
    if not value:
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def resolve_user_id(explicit: str | None) -> str:
    """Resolve the active user id for CLI commands.

    Resolution order:
    1) ``--user-id`` CLI argument
    2) ``DATAPULSE_USER_ID`` environment variable
    3) first user id found in ``recommendations``

    Args:
        explicit: ``--user-id`` argument value, if provided.

    Returns:
        User UUID as a string.

    Raises:
        RuntimeError: If no user id can be resolved.
    """
    if explicit and explicit.strip():
        return explicit.strip()

    env_user_id = os.getenv("DATAPULSE_USER_ID", "").strip()
    if env_user_id:
        return env_user_id

    client = get_client()
    try:
        result = client.table("recommendations").select("user_id").limit(1).execute()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "Failed to resolve user from recommendations. "
            "Set DATAPULSE_USER_ID or use --user-id."
        ) from exc

    rows = result.data or []
    if rows and rows[0].get("user_id"):
        return str(rows[0]["user_id"])

    raise RuntimeError("No user found. Set DATAPULSE_USER_ID or use --user-id.")


def _fetch_recommendations(
    *,
    client: Any,
    user_id: str,
    status: str,
) -> list[dict[str, Any]]:
    """Fetch recommendations for one user and status filter.

    Args:
        client: Supabase client instance.
        user_id: Target user UUID.
        status: One of pending/approved/rejected/all.

    Returns:
        Recommendation rows ordered by ``gap_rank`` then ``generated_at``.
    """
    query = (
        client.table("recommendations")
        .select(
            "id, user_id, skill_id, gap_rank, priority_tier, recommendation_text, "
            "resource_type, resource_url, estimated_hours, status, generated_at, "
            "reviewed_at, batch_id"
        )
        .eq("user_id", user_id)
        .order("gap_rank")
        .order("generated_at", desc=True)
    )
    if status != "all":
        query = query.eq("status", status)
    result = query.execute()
    return list(result.data or [])


def _fetch_status_counts(*, client: Any, user_id: str) -> dict[str, int]:
    """Return recommendation counts by status for one user.

    Args:
        client: Supabase client instance.
        user_id: Target user UUID.

    Returns:
        Dict with ``pending``, ``approved``, and ``rejected`` keys.
    """
    result = client.table("recommendations").select("status").eq("user_id", user_id).execute()
    rows = result.data or []
    counts = {"pending": 0, "approved": 0, "rejected": 0}
    for row in rows:
        status = str(row.get("status") or "").strip()
        if status in counts:
            counts[status] += 1
    return counts


def _fetch_skill_name_map(client: Any) -> dict[str, str]:
    """Build ``skill_id`` to display-name map from ``skills`` table.

    Args:
        client: Supabase client instance.

    Returns:
        Mapping from skill UUID to display string.
    """
    result = client.table("skills").select("id, display_name, name").execute()
    rows = result.data or []
    out: dict[str, str] = {}
    for row in rows:
        sid = row.get("id")
        if sid is None:
            continue
        display = row.get("display_name") or row.get("name") or "Unknown skill"
        out[str(sid)] = str(display)
    return out


def cmd_recommend_list(args: argparse.Namespace) -> None:
    """Handle ``recommend list`` subcommand.

    Args:
        args: Parsed argparse namespace.
    """
    status = str(args.status).strip().lower()
    if status not in ALLOWED_RECOMMEND_STATUSES:
        raise RuntimeError(
            f"Invalid --status value {status!r}. Use pending|approved|rejected|all."
        )

    user_id = resolve_user_id(args.user_id)
    client = get_client()

    try:
        rows = _fetch_recommendations(client=client, user_id=user_id, status=status)
        counts = _fetch_status_counts(client=client, user_id=user_id)
        skill_names = _fetch_skill_name_map(client)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Failed to load recommendations: {exc}") from exc

    if not rows:
        title = status.title() if status != "all" else "All"
        print(f"=== {title} Recommendations ===")
        print("")
        print("No recommendations found.")
        print("")
        print(
            f"Total: {counts['pending']} pending | {counts['approved']} approved | "
            f"{counts['rejected']} rejected"
        )
        return

    first_batch_id = str(rows[0].get("batch_id") or "n/a")
    title = status.title() if status != "all" else "All"
    print(f"=== {title} Recommendations (batch: {first_batch_id}) ===")
    print("")

    for idx, row in enumerate(rows, start=1):
        sid = row.get("skill_id")
        skill_name = skill_names.get(str(sid), "Unknown skill") if sid else "Unknown skill"
        tier = str(row.get("priority_tier") or "n/a")
        rank = row.get("gap_rank")
        rank_s = f"#{rank}" if rank is not None else "n/a"
        rec_text = str(row.get("recommendation_text") or "").strip()
        resource_type = str(row.get("resource_type") or "n/a")
        resource_url = str(row.get("resource_url") or "n/a")
        est_s = _format_hours(row.get("estimated_hours"))

        print(f"[{idx}] {skill_name} ({tier}, gap rank {rank_s})")
        print(f"    {rec_text}")
        print(f"    Resource: {resource_type} — {resource_url}")
        print(f"    Estimated: {est_s}")
        print(f"    ID: {row.get('id')}")
        print("")

    print(
        f"Total: {counts['pending']} pending | {counts['approved']} approved | "
        f"{counts['rejected']} rejected"
    )


def _fetch_pending_for_number_resolution(*, client: Any, user_id: str) -> list[dict[str, Any]]:
    """Fetch pending recommendations in stable display order.

    Args:
        client: Supabase client instance.
        user_id: Target user UUID.

    Returns:
        List of pending rows ordered exactly like ``recommend list`` default view.
    """
    return _fetch_recommendations(client=client, user_id=user_id, status="pending")


def _resolve_targets_to_ids(
    *,
    client: Any,
    user_id: str,
    tokens: list[str],
) -> list[str]:
    """Resolve CLI targets (numbers or UUIDs) into recommendation UUIDs.

    Args:
        client: Supabase client instance.
        user_id: Target user UUID.
        tokens: Positional arguments supplied to approve/reject/reset.

    Returns:
        Deduplicated recommendation UUID list preserving first-seen order.

    Raises:
        RuntimeError: If one or more tokens are invalid.
    """
    pending_rows = _fetch_pending_for_number_resolution(client=client, user_id=user_id)
    pending_ids_by_number: dict[int, str] = {
        idx: str(row["id"]) for idx, row in enumerate(pending_rows, start=1)
    }

    resolved: list[str] = []
    seen: set[str] = set()
    invalid_tokens: list[str] = []

    for token in tokens:
        trimmed = token.strip()
        if not trimmed:
            continue
        if trimmed.isdigit():
            num = int(trimmed)
            rid = pending_ids_by_number.get(num)
            if rid is None:
                invalid_tokens.append(trimmed)
                continue
        else:
            rid = trimmed
        if rid not in seen:
            resolved.append(rid)
            seen.add(rid)

    if invalid_tokens:
        joined = ", ".join(invalid_tokens)
        raise RuntimeError(f"Invalid recommendation number(s): {joined}")

    if not resolved:
        raise RuntimeError("No valid recommendation targets provided.")

    return resolved


def _apply_status_update(
    *,
    user_id: str,
    new_status: str,
    all_flag: bool,
    targets: list[str],
    allowed_current_statuses: set[str],
) -> int:
    """Apply a status update to matching recommendation rows.

    Args:
        user_id: Target user UUID.
        new_status: Status to set on matched rows.
        all_flag: Whether ``--all`` was passed.
        targets: Positional id/number targets from CLI.
        allowed_current_statuses: Rows must currently be in one of these statuses.

    Returns:
        Number of rows that were updated.
    """
    client = get_client()

    try:
        if all_flag:
            candidate_result = (
                client.table("recommendations")
                .select("id")
                .eq("user_id", user_id)
                .in_("status", sorted(allowed_current_statuses))
                .execute()
            )
            candidate_rows = candidate_result.data or []
            ids = [str(r["id"]) for r in candidate_rows if r.get("id") is not None]
        else:
            ids = _resolve_targets_to_ids(client=client, user_id=user_id, tokens=targets)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Failed to resolve recommendation targets: {exc}") from exc

    if not ids:
        return 0

    payload: dict[str, Any] = {"status": new_status}
    payload["reviewed_at"] = datetime.now(timezone.utc).isoformat()

    try:
        update_result = (
            client.table("recommendations")
            .update(payload)
            .eq("user_id", user_id)
            .in_("id", ids)
            .in_("status", sorted(allowed_current_statuses))
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Failed to update recommendations: {exc}") from exc

    updated_rows = update_result.data or []
    return len(updated_rows)


def cmd_recommend_approve(args: argparse.Namespace) -> None:
    """Handle ``recommend approve`` subcommand.

    Args:
        args: Parsed argparse namespace.
    """
    user_id = resolve_user_id(args.user_id)
    updated = _apply_status_update(
        user_id=user_id,
        new_status="approved",
        all_flag=bool(args.all),
        targets=list(args.targets or []),
        allowed_current_statuses={"pending"},
    )
    print(f"Approved {updated} recommendation(s).")


def cmd_recommend_reject(args: argparse.Namespace) -> None:
    """Handle ``recommend reject`` subcommand.

    Args:
        args: Parsed argparse namespace.
    """
    user_id = resolve_user_id(args.user_id)
    updated = _apply_status_update(
        user_id=user_id,
        new_status="rejected",
        all_flag=bool(args.all),
        targets=list(args.targets or []),
        allowed_current_statuses={"pending"},
    )
    print(f"Rejected {updated} recommendation(s).")


def cmd_recommend_reset(args: argparse.Namespace) -> None:
    """Handle ``recommend reset`` subcommand.

    Args:
        args: Parsed argparse namespace.
    """
    user_id = resolve_user_id(args.user_id)
    updated = _apply_status_update(
        user_id=user_id,
        new_status="pending",
        all_flag=bool(args.all),
        targets=list(args.targets or []),
        allowed_current_statuses=REVIEWABLE_STATUSES,
    )
    print(f"Reset {updated} recommendation(s) to pending.")


def _resolve_status_user_display_name(*, client: Any, user_id: str) -> str:
    """Load user display name for the status header.

    Args:
        client: Supabase client instance.
        user_id: Target user UUID.

    Returns:
        Display name when available, else ``"n/a"``.
    """
    result = (
        client.table("user_profiles")
        .select("display_name")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    rows = result.data or []
    if not rows:
        return "n/a"
    return str(rows[0].get("display_name") or "n/a")


def _latest_report_date() -> str:
    """Find most recent report file date from ``docs/reports``.

    Returns:
        ``YYYY-MM-DD`` from newest report filename when possible, else ``"n/a"``.
    """
    report_dir = _project_root() / "docs" / "reports"
    if not report_dir.is_dir():
        return "n/a"

    report_files = sorted(report_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not report_files:
        return "n/a"
    return report_files[0].stem


def _resolve_last_pipeline_run(*, client: Any) -> str:
    """Resolve last pipeline timestamp from recommendations or market signals.

    Args:
        client: Supabase client instance.

    Returns:
        ISO timestamp string or ``"n/a"``.
    """
    latest_rec = None
    latest_signal = None

    rec_result = (
        client.table("recommendations")
        .select("generated_at")
        .order("generated_at", desc=True)
        .limit(1)
        .execute()
    )
    rec_rows = rec_result.data or []
    if rec_rows:
        latest_rec = _parse_iso_timestamp(str(rec_rows[0].get("generated_at") or ""))

    signal_result = (
        client.table("market_signals")
        .select("extracted_at")
        .order("extracted_at", desc=True)
        .limit(1)
        .execute()
    )
    signal_rows = signal_result.data or []
    if signal_rows:
        latest_signal = _parse_iso_timestamp(str(signal_rows[0].get("extracted_at") or ""))

    candidates = [dt for dt in (latest_rec, latest_signal) if dt is not None]
    if not candidates:
        return "n/a"
    return max(candidates).isoformat().replace("+00:00", "Z")


def cmd_status(args: argparse.Namespace) -> None:
    """Handle ``status`` subcommand.

    Args:
        args: Parsed argparse namespace.
    """
    user_id = resolve_user_id(args.user_id)
    client = get_client()

    try:
        display_name = _resolve_status_user_display_name(client=client, user_id=user_id)

        user_skills_result = (
            client.table("user_skills").select("id", count="exact").eq("user_id", user_id).execute()
        )
        skills_count = int(user_skills_result.count or 0)

        signals_result = client.table("market_signals").select("id, skill_id").execute()
        signals_rows = signals_result.data or []
        signals_total = len(signals_rows)
        mapped_total = sum(1 for row in signals_rows if row.get("skill_id") is not None)
        mapped_percent = int(round((mapped_total / signals_total) * 100)) if signals_total else 0

        rec_counts = _fetch_status_counts(client=client, user_id=user_id)
        last_report = _latest_report_date()
        last_pipeline = _resolve_last_pipeline_run(client=client)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Failed to build status overview: {exc}") from exc

    print("=== DataPulse Status ===")
    print(f"User: {display_name} (user_id: {user_id})")
    print(f"Skills in profile: {skills_count}")
    print(f"Market signals: {signals_total} ({mapped_percent}% mapped)")
    print(
        "Recommendations: "
        f"{rec_counts['pending']} pending, "
        f"{rec_counts['approved']} approved, "
        f"{rec_counts['rejected']} rejected"
    )
    print(f"Last report: {last_report}")
    print(f"Last pipeline run: {last_pipeline}")


def _validate_target_arguments(args: argparse.Namespace) -> None:
    """Validate positional target arguments for review subcommands.

    Args:
        args: Parsed argparse namespace for approve/reject/reset.

    Raises:
        RuntimeError: If arguments are invalid.
    """
    all_flag = bool(getattr(args, "all", False))
    targets = list(getattr(args, "targets", []) or [])
    if all_flag and targets:
        raise RuntimeError("Use either positional targets or --all, not both.")
    if not all_flag and not targets:
        raise RuntimeError("Provide recommendation ID/number targets, or use --all.")


def build_parser() -> argparse.ArgumentParser:
    """Create and configure argparse parser tree for DataPulse CLI.

    Returns:
        Top-level argument parser.
    """
    parser = argparse.ArgumentParser(
        prog="datapulse",
        description="DataPulse command-line tools.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # ``status`` command.
    status_parser = subparsers.add_parser("status", help="Show DataPulse status overview.")
    status_parser.add_argument("--user-id", type=str, default=None, metavar="UUID")
    status_parser.set_defaults(handler=cmd_status)

    # ``recommend`` command group.
    recommend_parser = subparsers.add_parser("recommend", help="Manage recommendations.")
    recommend_subparsers = recommend_parser.add_subparsers(dest="recommend_command", required=True)

    list_parser = recommend_subparsers.add_parser("list", help="List recommendations.")
    list_parser.add_argument("--user-id", type=str, default=None, metavar="UUID")
    list_parser.add_argument(
        "--status",
        type=str,
        default="pending",
        metavar="pending|approved|rejected|all",
    )
    list_parser.set_defaults(handler=cmd_recommend_list)

    approve_parser = recommend_subparsers.add_parser(
        "approve",
        help="Approve recommendations by number or id.",
    )
    approve_parser.add_argument("targets", nargs="*", help="Display number(s) or recommendation UUID(s).")
    approve_parser.add_argument("--all", action="store_true", help="Approve all pending recommendations.")
    approve_parser.add_argument("--user-id", type=str, default=None, metavar="UUID")
    approve_parser.set_defaults(handler=cmd_recommend_approve)

    reject_parser = recommend_subparsers.add_parser(
        "reject",
        help="Reject recommendations by number or id.",
    )
    reject_parser.add_argument("targets", nargs="*", help="Display number(s) or recommendation UUID(s).")
    reject_parser.add_argument("--all", action="store_true", help="Reject all pending recommendations.")
    reject_parser.add_argument("--user-id", type=str, default=None, metavar="UUID")
    reject_parser.set_defaults(handler=cmd_recommend_reject)

    reset_parser = recommend_subparsers.add_parser(
        "reset",
        help="Reset recommendations back to pending.",
    )
    reset_parser.add_argument("targets", nargs="*", help="Recommendation UUID(s) or display number(s).")
    reset_parser.add_argument(
        "--all",
        action="store_true",
        help="Reset all approved/rejected recommendations to pending.",
    )
    reset_parser.add_argument("--user-id", type=str, default=None, metavar="UUID")
    reset_parser.set_defaults(handler=cmd_recommend_reset)

    return parser


def main() -> None:
    """Run DataPulse CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args()

    try:
        if getattr(args, "recommend_command", None) in {"approve", "reject", "reset"}:
            _validate_target_arguments(args)
        handler = args.handler
        handler(args)
    except RuntimeError as exc:
        parser.exit(status=1, message=f"Error: {exc}\n")


if __name__ == "__main__":
    main()

