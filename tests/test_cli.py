"""Tests for CLI argument parsing and helpers."""

from __future__ import annotations

import sys

import pytest

from datapulse import cli


def test_cli_help_exits_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    """Main should exit with code 0 when called with --help."""
    monkeypatch.setattr(sys, "argv", ["datapulse", "--help"])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 0


def test_cli_status_subcommand_parses() -> None:
    """Parser should recognize the status command."""
    parser = cli.build_parser()
    args = parser.parse_args(["status"])
    assert args.command == "status"


def test_cli_recommend_list_parses() -> None:
    """Parser should recognize recommend list command."""
    parser = cli.build_parser()
    args = parser.parse_args(["recommend", "list"])
    assert args.command == "recommend"
    assert args.recommend_command == "list"


def test_cli_recommend_approve_parses() -> None:
    """Parser should parse approve targets."""
    parser = cli.build_parser()
    args = parser.parse_args(["recommend", "approve", "1", "2"])
    assert args.command == "recommend"
    assert args.recommend_command == "approve"
    assert args.targets == ["1", "2"]
