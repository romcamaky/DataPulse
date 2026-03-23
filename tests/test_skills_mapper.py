"""Tests for SkillsMapper matching logic."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from datapulse.skills_mapper import SkillsMapper


def _make_mock_client(rows: list[dict[str, object]]) -> MagicMock:
    """Build a mock Supabase client that returns supplied skill rows."""
    response = SimpleNamespace(data=rows)
    client = MagicMock()
    client.table.return_value.select.return_value.execute.return_value = response
    return client


@patch("datapulse.skills_mapper.get_client")
def test_map_skill_exact_name(
    mock_get_client: MagicMock,
    sample_skills_db: list[dict[str, object]],
) -> None:
    """Exact canonical name should map directly to matching id."""
    mock_get_client.return_value = _make_mock_client(sample_skills_db)
    mapper = SkillsMapper()
    assert mapper.map_skill("python") == "sk-python"


@patch("datapulse.skills_mapper.get_client")
def test_map_skill_display_name(
    mock_get_client: MagicMock,
    sample_skills_db: list[dict[str, object]],
) -> None:
    """Display name lookup should be case-insensitive."""
    mock_get_client.return_value = _make_mock_client(sample_skills_db)
    mapper = SkillsMapper()
    assert mapper.map_skill("Python") == "sk-python"


@patch("datapulse.skills_mapper.get_client")
def test_map_skill_alias(
    mock_get_client: MagicMock,
    sample_skills_db: list[dict[str, object]],
) -> None:
    """Alias should resolve through canonical target name."""
    mock_get_client.return_value = _make_mock_client(sample_skills_db)
    mapper = SkillsMapper()
    assert mapper.map_skill("postgres") == "sk-postgresql"


@patch("datapulse.skills_mapper.get_client")
def test_map_skill_unknown(
    mock_get_client: MagicMock,
    sample_skills_db: list[dict[str, object]],
) -> None:
    """Unknown skill names should return None."""
    mock_get_client.return_value = _make_mock_client(sample_skills_db)
    mapper = SkillsMapper()
    assert mapper.map_skill("nonexistent_skill_xyz") is None


@pytest.mark.parametrize("value", ["PYTHON", "Python", "pYtHoN"])
@patch("datapulse.skills_mapper.get_client")
def test_map_skill_case_insensitive(
    mock_get_client: MagicMock,
    value: str,
    sample_skills_db: list[dict[str, object]],
) -> None:
    """Name matching should be case-insensitive."""
    mock_get_client.return_value = _make_mock_client(sample_skills_db)
    mapper = SkillsMapper()
    assert mapper.map_skill(value) == "sk-python"


@patch("datapulse.skills_mapper.get_client")
def test_map_skills_bulk(
    mock_get_client: MagicMock,
    sample_skills_db: list[dict[str, object]],
) -> None:
    """Bulk mapping should preserve input order and mixed resolution."""
    mock_get_client.return_value = _make_mock_client(sample_skills_db)
    mapper = SkillsMapper()
    result = mapper.map_skills(["python", "PostgreSQL", "postgres", "missing"])
    assert result == [
        ("python", "sk-python"),
        ("PostgreSQL", "sk-postgresql"),
        ("postgres", "sk-postgresql"),
        ("missing", None),
    ]
