"""Tests for extractor skill resolution logic."""

from __future__ import annotations

from datapulse.extractor import SkillIndex, load_skill_index, resolve_skill_id


def _build_index(sample_skills_db: list[dict[str, object]]) -> SkillIndex:
    """Build extractor SkillIndex from fixture rows."""
    return load_skill_index(sample_skills_db)  # type: ignore[arg-type]


def test_resolve_skill_id_exact_name(sample_skills_db: list[dict[str, object]]) -> None:
    """Exact canonical name should map directly."""
    index = _build_index(sample_skills_db)
    assert resolve_skill_id("python", index) == "sk-python"


def test_resolve_skill_id_display_name(sample_skills_db: list[dict[str, object]]) -> None:
    """Display name should resolve case-insensitively."""
    index = _build_index(sample_skills_db)
    assert resolve_skill_id("Python", index) == "sk-python"


def test_resolve_skill_id_alias(sample_skills_db: list[dict[str, object]]) -> None:
    """Alias keys should resolve through SKILL_ALIASES."""
    index = _build_index(sample_skills_db)
    assert resolve_skill_id("chatgpt", index) == "sk-llm"


def test_resolve_skill_id_compact_form(sample_skills_db: list[dict[str, object]]) -> None:
    """Compact underscore fallback should catch punctuation-separated forms."""
    rows = list(sample_skills_db) + [
        {
            "id": "sk-kafka",
            "name": "apache_kafka",
            "display_name": "Apache Kafka",
            "category": "framework",
            "parent_skill_id": None,
        }
    ]
    index = _build_index(rows)
    assert resolve_skill_id("Apache-Kafka", index) == "sk-kafka"


def test_resolve_skill_id_unknown(sample_skills_db: list[dict[str, object]]) -> None:
    """Unknown skill names should return None."""
    index = _build_index(sample_skills_db)
    assert resolve_skill_id("nonexistent_thing", index) is None
