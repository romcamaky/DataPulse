"""Shared pytest fixtures for DataPulse tests."""

from __future__ import annotations

import os

import pytest

# Ensure imports that validate config at import-time do not fail in tests.
os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-key")


@pytest.fixture
def sample_skills_db() -> list[dict[str, object]]:
    """Minimal skills table data for testing mappers without Supabase."""
    return [
        {
            "id": "sk-python",
            "name": "python",
            "display_name": "Python",
            "category": "language",
            "parent_skill_id": None,
        },
        {
            "id": "sk-sql",
            "name": "sql",
            "display_name": "SQL",
            "category": "language",
            "parent_skill_id": None,
        },
        {
            "id": "sk-dbt",
            "name": "dbt",
            "display_name": "dbt",
            "category": "tool",
            "parent_skill_id": None,
        },
        {
            "id": "sk-postgresql",
            "name": "postgresql",
            "display_name": "PostgreSQL",
            "category": "platform",
            "parent_skill_id": None,
        },
        {
            "id": "sk-docker",
            "name": "docker",
            "display_name": "Docker",
            "category": "tool",
            "parent_skill_id": None,
        },
        {
            "id": "sk-llm",
            "name": "llm_integration",
            "display_name": "LLM Integration",
            "category": "concept",
            "parent_skill_id": None,
        },
        {
            "id": "sk-rag",
            "name": "rag",
            "display_name": "RAG",
            "category": "concept",
            "parent_skill_id": None,
        },
        {
            "id": "sk-ml",
            "name": "machine_learning",
            "display_name": "Machine Learning",
            "category": "concept",
            "parent_skill_id": None,
        },
        {
            "id": "sk-agents",
            "name": "ai_agents",
            "display_name": "AI Agents",
            "category": "concept",
            "parent_skill_id": None,
        },
        {
            "id": "sk-etl",
            "name": "etl_design",
            "display_name": "ETL/ELT Design",
            "category": "concept",
            "parent_skill_id": None,
        },
        {
            "id": "sk-power_bi",
            "name": "power_bi",
            "display_name": "Power BI",
            "category": "tool",
            "parent_skill_id": None,
        },
        {
            "id": "sk-aws",
            "name": "aws",
            "display_name": "AWS",
            "category": "platform",
            "parent_skill_id": None,
        },
        {
            "id": "sk-gcp",
            "name": "gcp",
            "display_name": "GCP",
            "category": "platform",
            "parent_skill_id": None,
        },
        {
            "id": "sk-gen-ai",
            "name": "generative_ai",
            "display_name": "Generative AI",
            "category": "concept",
            "parent_skill_id": None,
        },
        {
            "id": "sk-pe",
            "name": "prompt_engineering",
            "display_name": "Prompt Engineering",
            "category": "concept",
            "parent_skill_id": None,
        },
        {
            "id": "sk-spark",
            "name": "spark",
            "display_name": "Apache Spark",
            "category": "framework",
            "parent_skill_id": None,
        },
        {
            "id": "sk-airflow",
            "name": "airflow",
            "display_name": "Apache Airflow",
            "category": "framework",
            "parent_skill_id": None,
        },
        {
            "id": "sk-governance",
            "name": "data_governance",
            "display_name": "Data Governance",
            "category": "concept",
            "parent_skill_id": None,
        },
    ]


@pytest.fixture
def sample_gap_rows() -> list[dict[str, object]]:
    """Sample gap analysis rows for recommender tests."""
    return [
        {
            "skill_id": "sk-python",
            "skill_display_name": "Python",
            "user_level": 2,
            "demand_score": 8.5,
            "gap_score": 6.5,
            "gap_rank": 1,
            "gap_category": "critical",
            "priority_tier": "critical",
            "signal_count": 26,
        },
        {
            "skill_id": "sk-dbt",
            "skill_display_name": "dbt",
            "user_level": 3,
            "demand_score": 5.0,
            "gap_score": 2.0,
            "gap_rank": 5,
            "gap_category": "important",
            "priority_tier": "important",
            "signal_count": 18,
        },
        {
            "skill_id": "sk-docker",
            "skill_display_name": "Docker",
            "user_level": 0,
            "demand_score": 3.0,
            "gap_score": 3.0,
            "gap_rank": 3,
            "gap_category": "critical",
            "priority_tier": "critical",
            "signal_count": 6,
        },
    ]
