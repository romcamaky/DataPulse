-- ============================================================
-- DataPulse Phase 0A: Skill Alias Normalization — Schema Migration
-- Migration: 005_skill_aliases.sql
-- Date: 2026-03-23
-- Description: Adds missing canonical skills that appear frequently
--              in market signals but were absent from the skills table,
--              preventing skill_id resolution (~80% NULL rate).
-- ============================================================

-- UP: Insert new top-level and child skills
-- Why: The extractor produces skill_name_raw values for concepts like
--      "machine learning", "generative ai", "ai agents", etc. that have
--      no matching row in skills. Adding them lets the alias resolver
--      map these names to a skill_id.

-- ------------------------------------------------------------
-- Step 1: Top-level skills (no parent)
-- Uses ON CONFLICT to be idempotent if re-run.
-- ------------------------------------------------------------
INSERT INTO public.skills (name, display_name, category, parent_skill_id)
VALUES
  ('machine_learning', 'Machine Learning', 'concept', NULL),
  ('deep_learning', 'Deep Learning', 'concept', NULL),
  ('reinforcement_learning', 'Reinforcement Learning', 'concept', NULL),
  ('generative_ai', 'Generative AI', 'concept', NULL),
  ('ai_agents', 'AI Agents', 'concept', NULL),
  ('natural_language_processing', 'Natural Language Processing', 'concept', NULL),
  ('computer_vision', 'Computer Vision', 'concept', NULL),
  ('ai_safety', 'AI Safety', 'concept', NULL),
  ('ai_governance', 'AI Governance', 'concept', NULL),
  ('data_engineering', 'Data Engineering', 'concept', NULL),
  ('analytics_engineering', 'Analytics Engineering', 'concept', NULL),
  ('data_science', 'Data Science', 'concept', NULL),
  ('excel', 'Excel', 'tool', NULL),
  ('apache_kafka', 'Apache Kafka', 'framework', NULL),
  ('apache_iceberg', 'Apache Iceberg', 'framework', NULL),
  ('vector_databases', 'Vector Databases', 'concept', NULL),
  ('fine_tuning', 'Fine-Tuning (LLMs)', 'concept', NULL),
  ('mlops', 'MLOps', 'concept', NULL),
  ('data_observability', 'Data Observability', 'concept', NULL),
  ('microsoft_fabric', 'Microsoft Fabric', 'platform', NULL),
  ('amazon_redshift', 'Amazon Redshift', 'platform', NULL),
  ('oracle', 'Oracle Database', 'platform', NULL),
  ('mysql', 'MySQL', 'platform', NULL),
  ('clickhouse', 'ClickHouse', 'platform', NULL),
  ('java', 'Java', 'language', NULL),
  ('fastapi', 'FastAPI', 'framework', NULL),
  ('pytorch', 'PyTorch', 'framework', NULL),
  ('data_mesh', 'Data Mesh', 'concept', NULL),
  ('lakehouse', 'Lakehouse Architecture', 'concept', NULL),
  ('ms_sql_server', 'MS SQL Server', 'platform', NULL)
ON CONFLICT (name) DO UPDATE
SET display_name = EXCLUDED.display_name,
    category = EXCLUDED.category;

-- ------------------------------------------------------------
-- Step 2: Child skills (resolve parent by name)
-- Why: Some new skills have a clear parent relationship
--      (e.g. "OpenAI API" → llm_integration, "MCP" → ai_agents).
-- ------------------------------------------------------------
WITH child_rows AS (
  SELECT *
  FROM (VALUES
    ('openai_api', 'OpenAI API', 'tool', 'llm_integration'),
    ('claude_api', 'Claude API', 'tool', 'llm_integration'),
    ('embedding_models', 'Embedding Models', 'concept', 'natural_language_processing'),
    ('transformer_models', 'Transformer Models', 'concept', 'deep_learning'),
    ('mcp', 'Model Context Protocol (MCP)', 'concept', 'ai_agents')
  ) AS v(name, display_name, category, parent_name)
),
parents AS (
  SELECT id, name FROM public.skills
)
INSERT INTO public.skills (name, display_name, category, parent_skill_id)
SELECT c.name, c.display_name, c.category, p.id
FROM child_rows c
JOIN parents p ON p.name = c.parent_name
ON CONFLICT (name) DO UPDATE
SET display_name = EXCLUDED.display_name,
    category = EXCLUDED.category,
    parent_skill_id = EXCLUDED.parent_skill_id;

-- ============================================================
-- Verification query (manual):
-- SELECT count(*) AS total_skills FROM public.skills;
-- Expected: ~86 rows (51 original + 30 top-level + 5 child)
-- ============================================================

-- ============================================================
-- To rollback, remove the new rows:
-- DELETE FROM public.skills WHERE name IN (
--   'machine_learning', 'deep_learning', 'reinforcement_learning',
--   'generative_ai', 'ai_agents', 'natural_language_processing',
--   'computer_vision', 'ai_safety', 'ai_governance', 'data_engineering',
--   'analytics_engineering', 'data_science', 'excel', 'apache_kafka',
--   'apache_iceberg', 'vector_databases', 'fine_tuning', 'mlops',
--   'data_observability', 'microsoft_fabric', 'amazon_redshift',
--   'oracle', 'mysql', 'clickhouse', 'java', 'fastapi', 'pytorch',
--   'data_mesh', 'lakehouse', 'ms_sql_server',
--   'openai_api', 'claude_api', 'embedding_models',
--   'transformer_models', 'mcp'
-- );
-- ============================================================
