"""Tests for the shared skill alias mappings."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from datapulse.skill_aliases import SKILL_ALIASES


def test_all_alias_keys_are_lowercase() -> None:
    """Every alias key should already be normalized (lowercase and stripped)."""
    for key in SKILL_ALIASES:
        assert key == key.lower()
        assert key == key.strip()


def test_no_alias_maps_to_itself() -> None:
    """Alias entries should map to canonical names, not identity mappings."""
    for alias, target in SKILL_ALIASES.items():
        assert alias != target


@pytest.mark.parametrize(
    ("alias", "expected"),
    [
        ("machine learning", "machine_learning"),
        ("ai agents", "ai_agents"),
        ("chatgpt", "llm_integration"),
        ("gpt-4", "llm_integration"),
        ("postgres", "postgresql"),
        ("pyspark", "spark"),
        ("etl/elt", "etl_design"),
        ("power bi", "power_bi"),
        ("kubernetes", "docker"),
        ("amazon web services", "aws"),
        ("generative ai", "generative_ai"),
        ("dbt core", "dbt"),
        ("apache kafka", "apache_kafka"),
        ("retrieval-augmented generation", "rag"),
        ("claude", "llm_integration"),
    ],
)
def test_known_aliases_resolve(alias: str, expected: str) -> None:
    """Critical aliases should resolve to expected canonical names."""
    assert SKILL_ALIASES[alias] == expected


def test_alias_targets_are_valid_skill_names() -> None:
    """Alias targets should look like canonical skill names."""
    pattern = re.compile(r"^[a-z0-9_]+$")
    for target in SKILL_ALIASES.values():
        assert target == target.strip()
        assert pattern.match(target) is not None


def test_no_duplicate_keys() -> None:
    """Source file should not contain duplicate key lines."""
    root = Path(__file__).resolve().parents[1]
    content = (root / "src" / "datapulse" / "skill_aliases.py").read_text(encoding="utf-8")
    key_lines = re.findall(r'^\s*"([^"]+)":\s*"', content, flags=re.MULTILINE)
    assert len(key_lines) == len(set(key_lines))
