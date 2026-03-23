"""Tests for recommender pure logic (no API calls)."""

from __future__ import annotations

import re

from datapulse.recommender import (
    RecommenderRunStats,
    _format_json_field,
    _normalize_skill_key,
    build_gap_skill_lookup,
    build_user_message,
    generate_batch_id,
    validate_recommendation_row,
)


def test_normalize_skill_key() -> None:
    """Skill key normalization should trim, lowercase, and collapse spaces."""
    assert _normalize_skill_key("  Python  ") == "python"
    assert _normalize_skill_key("Apache  Spark") == "apache spark"


def test_build_gap_skill_lookup(sample_gap_rows: list[dict[str, object]]) -> None:
    """Gap lookup should index normalized display names to skill ids."""
    lookup = build_gap_skill_lookup(sample_gap_rows)
    assert lookup["python"] == "sk-python"
    assert lookup["dbt"] == "sk-dbt"
    assert lookup["docker"] == "sk-docker"


def test_validate_recommendation_row_valid() -> None:
    """A valid recommendation payload should pass validation."""
    stats = RecommenderRunStats()
    row = validate_recommendation_row(
        {
            "skill_name": "Python",
            "gap_rank": 1,
            "priority_tier": "critical",
            "recommendation_text": "Practice Pandas and build one ETL mini-project.",
            "resource_type": "tutorial",
            "resource_url": "https://example.com/python",
            "estimated_hours": 8,
        },
        gap_lookup={"python": "sk-python"},
        stats=stats,
    )
    assert row is not None
    assert row["skill_id"] == "sk-python"
    assert row["priority_tier"] == "critical"
    assert stats.unmapped_skill_warnings == 0


def test_validate_recommendation_row_missing_skill_name() -> None:
    """Missing skill_name should fail validation."""
    stats = RecommenderRunStats()
    row = validate_recommendation_row(
        {
            "gap_rank": 1,
            "priority_tier": "critical",
            "recommendation_text": "Text.",
            "resource_type": "tutorial",
        },
        gap_lookup={},
        stats=stats,
    )
    assert row is None


def test_validate_recommendation_row_missing_text() -> None:
    """Missing recommendation_text should fail validation."""
    stats = RecommenderRunStats()
    row = validate_recommendation_row(
        {
            "skill_name": "Python",
            "gap_rank": 1,
            "priority_tier": "critical",
            "resource_type": "tutorial",
        },
        gap_lookup={"python": "sk-python"},
        stats=stats,
    )
    assert row is None


def test_validate_recommendation_row_invalid_resource_type() -> None:
    """Unsupported resource_type should fail validation."""
    stats = RecommenderRunStats()
    row = validate_recommendation_row(
        {
            "skill_name": "Python",
            "gap_rank": 1,
            "priority_tier": "critical",
            "recommendation_text": "Text.",
            "resource_type": "video",
        },
        gap_lookup={"python": "sk-python"},
        stats=stats,
    )
    assert row is None


def test_validate_recommendation_row_invalid_priority() -> None:
    """Unsupported priority_tier should fail validation."""
    stats = RecommenderRunStats()
    row = validate_recommendation_row(
        {
            "skill_name": "Python",
            "gap_rank": 1,
            "priority_tier": "urgent",
            "recommendation_text": "Text.",
            "resource_type": "tutorial",
        },
        gap_lookup={"python": "sk-python"},
        stats=stats,
    )
    assert row is None


def test_validate_recommendation_row_unmapped_skill() -> None:
    """Unknown skill names should set skill_id to None and increment warning."""
    stats = RecommenderRunStats()
    row = validate_recommendation_row(
        {
            "skill_name": "Unknown Skill",
            "gap_rank": 2,
            "priority_tier": "important",
            "recommendation_text": "Text.",
            "resource_type": "course",
            "estimated_hours": 4,
        },
        gap_lookup={"python": "sk-python"},
        stats=stats,
    )
    assert row is not None
    assert row["skill_id"] is None
    assert stats.unmapped_skill_warnings == 1


def test_generate_batch_id_format() -> None:
    """Batch id should follow YYYY-MM-DD_xxxxxxxx format."""
    value = generate_batch_id("a1b2c3d4-aaaa-bbbb-cccc-ddddeeeeffff")
    assert re.match(r"^\d{4}-\d{2}-\d{2}_[a-z0-9]{8}$", value)


def test_format_json_field_none() -> None:
    """None values should render as n/a."""
    assert _format_json_field(None) == "n/a"


def test_format_json_field_list() -> None:
    """List values should be JSON-encoded."""
    assert _format_json_field(["a", "b"]) == '["a", "b"]'


def test_build_user_message_contains_sections(
    sample_gap_rows: list[dict[str, object]],
) -> None:
    """Rendered prompt should include core context sections."""
    msg = build_user_message(
        profile={
            "display_name": "Romi",
            "role_title": "Data Analyst",
            "industry": "Tech",
            "country": "CZ",
            "years_total_experience": 3,
            "weekly_hours_available": 6,
            "learning_preferences": ["hands-on"],
            "course_completion_rate": "medium",
            "learning_failures": "None",
            "work_frustrations": "Slow reporting",
            "ai_usage_frequency": "weekly",
            "ai_api_experience": "beginner",
            "platform_access": ["Coursera"],
            "career_narrative": "Wants to move into analytics engineering.",
        },
        target_roles=[{"role_name": "Analytics Engineer", "priority": 1}],
        gaps=sample_gap_rows,
        trends=[{"skill_display_name": "Python", "signal_count": 10, "avg_strength": 4.0, "trending_score": 12.5}],
    )
    assert "## User Profile" in msg
    assert "## Skill Gaps" in msg
    assert "## Current Market Trends" in msg
