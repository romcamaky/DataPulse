-- ============================================================
-- DataPulse Module 1: Profile Engine — Schema Migration
-- Migration: 001_module1_schema.sql
-- Date: 2026-03-17
-- Description: Creates core tables for user profiling system
-- ============================================================

-- UP: Create tables, policies, triggers, seed data
-- Why: Establishes the foundational schema for user profiles, skills, and work experience
--      with safe multi-tenant access via Supabase RLS.

-- ------------------------------------------------------------
-- Table 1/6: skills
-- What: Canonical, shared skill reference table (not per-user).
-- Why: Enables consistent skill identifiers across all users and features (gap analysis, trends).
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.skills (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL UNIQUE,
  display_name text NOT NULL,
  parent_skill_id uuid NULL REFERENCES public.skills(id),
  category text NOT NULL CHECK (category IN ('language', 'framework', 'tool', 'platform', 'concept', 'soft_skill')),
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.skills ENABLE ROW LEVEL SECURITY;

-- What: Allow any authenticated user to read the skill catalog.
-- Why: The skills table is shared reference data and must be readable across tenants.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_policies
    WHERE schemaname = 'public'
      AND tablename = 'skills'
      AND policyname = 'Skills are readable by authenticated users'
  ) THEN
    CREATE POLICY "Skills are readable by authenticated users"
      ON public.skills
      FOR SELECT
      TO authenticated
      USING (true);
  END IF;
END $$;

-- ------------------------------------------------------------
-- Table 2/6: user_profiles
-- What: One profile row per user (Supabase auth.users).
-- Why: Central place for user identity + career context used by downstream personalization.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.user_profiles (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL UNIQUE REFERENCES auth.users(id) ON DELETE CASCADE,
  display_name text NOT NULL,
  email text NOT NULL,
  bio text,
  career_narrative text,
  role_title text,
  company_name text,
  company_size text CHECK (company_size IN ('solo', 'small', 'medium', 'large', 'enterprise')),
  industry text,
  years_in_current_role smallint,
  years_total_experience smallint,
  country text,
  city text,
  timezone text,
  remote_preference text CHECK (remote_preference IN ('remote_only', 'hybrid', 'onsite', 'flexible')),
  weekly_hours_available smallint,
  learning_preferences text[],
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.user_profiles ENABLE ROW LEVEL SECURITY;

-- What: Users can read only their own profile.
-- Why: Profile contains private career details and must be tenant-isolated.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_policies
    WHERE schemaname = 'public'
      AND tablename = 'user_profiles'
      AND policyname = 'Users select their own profile'
  ) THEN
    CREATE POLICY "Users select their own profile"
      ON public.user_profiles
      FOR SELECT
      TO authenticated
      USING (auth.uid() = user_id);
  END IF;
END $$;

-- What: Users can create their own profile row.
-- Why: Initial onboarding writes should be allowed without service-role access.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_policies
    WHERE schemaname = 'public'
      AND tablename = 'user_profiles'
      AND policyname = 'Users insert their own profile'
  ) THEN
    CREATE POLICY "Users insert their own profile"
      ON public.user_profiles
      FOR INSERT
      TO authenticated
      WITH CHECK (auth.uid() = user_id);
  END IF;
END $$;

-- What: Users can update only their own profile row.
-- Why: Prevents cross-user edits while allowing profile maintenance.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_policies
    WHERE schemaname = 'public'
      AND tablename = 'user_profiles'
      AND policyname = 'Users update their own profile'
  ) THEN
    CREATE POLICY "Users update their own profile"
      ON public.user_profiles
      FOR UPDATE
      TO authenticated
      USING (auth.uid() = user_id)
      WITH CHECK (auth.uid() = user_id);
  END IF;
END $$;

-- Note: No DELETE policy for user_profiles.
-- Why: Profiles should be deactivated rather than hard-deleted by end users.

-- ------------------------------------------------------------
-- Table 3/6: user_target_roles
-- What: Multiple target roles per user (ranked by priority).
-- Why: Drives personalization toward the roles the user wants next.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.user_target_roles (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  role_name text NOT NULL,
  priority smallint NOT NULL DEFAULT 1,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (user_id, role_name)
);

ALTER TABLE public.user_target_roles ENABLE ROW LEVEL SECURITY;

-- What: Users manage only their own target roles (full CRUD).
-- Why: Target roles are user-owned preference data and must be tenant-isolated.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_policies
    WHERE schemaname = 'public'
      AND tablename = 'user_target_roles'
      AND policyname = 'Users manage their own target roles'
  ) THEN
    CREATE POLICY "Users manage their own target roles"
      ON public.user_target_roles
      FOR ALL
      TO authenticated
      USING (auth.uid() = user_id)
      WITH CHECK (auth.uid() = user_id);
  END IF;
END $$;

-- ------------------------------------------------------------
-- Table 4/6: user_skills
-- What: User-skill assessments linked to canonical skills.
-- Why: Captures a structured skills profile for gap analysis and recommendations.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.user_skills (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  skill_id uuid NOT NULL REFERENCES public.skills(id),
  level smallint NOT NULL CHECK (level BETWEEN 1 AND 5),
  confidence text NOT NULL CHECK (confidence IN ('low', 'medium', 'high')),
  evidence_type text NOT NULL CHECK (evidence_type IN ('github', 'work', 'course', 'self_assessment')),
  evidence_detail text,
  visibility text NOT NULL DEFAULT 'public' CHECK (visibility IN ('public', 'private', 'confidential')),
  last_assessed_at timestamptz NOT NULL DEFAULT now(),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (user_id, skill_id)
);

ALTER TABLE public.user_skills ENABLE ROW LEVEL SECURITY;

-- What: Users manage only their own skill assessments (full CRUD).
-- Why: Skill levels and evidence are sensitive and must be tenant-isolated.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_policies
    WHERE schemaname = 'public'
      AND tablename = 'user_skills'
      AND policyname = 'Users manage their own skills'
  ) THEN
    CREATE POLICY "Users manage their own skills"
      ON public.user_skills
      FOR ALL
      TO authenticated
      USING (auth.uid() = user_id)
      WITH CHECK (auth.uid() = user_id);
  END IF;
END $$;

-- ------------------------------------------------------------
-- Table 5/6: work_experience
-- What: User-entered work experience entries (roles at companies).
-- Why: Provides context for narrative parsing and supports linking skills to experience.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.work_experience (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  role_title text NOT NULL,
  company_name text NOT NULL,
  start_date date NOT NULL,
  end_date date,
  description text,
  is_confidential boolean NOT NULL DEFAULT false,
  visibility text NOT NULL DEFAULT 'public' CHECK (visibility IN ('public', 'private', 'confidential')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.work_experience ENABLE ROW LEVEL SECURITY;

-- What: Users manage only their own work experience (full CRUD).
-- Why: Work history is personal data and must be tenant-isolated.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_policies
    WHERE schemaname = 'public'
      AND tablename = 'work_experience'
      AND policyname = 'Users manage their own work experience'
  ) THEN
    CREATE POLICY "Users manage their own work experience"
      ON public.work_experience
      FOR ALL
      TO authenticated
      USING (auth.uid() = user_id)
      WITH CHECK (auth.uid() = user_id);
  END IF;
END $$;

-- ------------------------------------------------------------
-- Table 6/6: work_experience_skills
-- What: Junction table linking work experience entries to canonical skills.
-- Why: Normalizes the many-to-many relationship without duplicating skill text arrays.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.work_experience_skills (
  work_experience_id uuid NOT NULL REFERENCES public.work_experience(id) ON DELETE CASCADE,
  skill_id uuid NOT NULL REFERENCES public.skills(id),
  PRIMARY KEY (work_experience_id, skill_id)
);

ALTER TABLE public.work_experience_skills ENABLE ROW LEVEL SECURITY;

-- What: Users manage only links that belong to their work experience.
-- Why: Prevents creating or reading cross-user associations via the junction table.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_policies
    WHERE schemaname = 'public'
      AND tablename = 'work_experience_skills'
      AND policyname = 'Users manage their own work_experience_skills'
  ) THEN
    CREATE POLICY "Users manage their own work_experience_skills"
      ON public.work_experience_skills
      FOR ALL
      TO authenticated
      USING (
        work_experience_id IN (
          SELECT id FROM public.work_experience WHERE user_id = auth.uid()
        )
      )
      WITH CHECK (
        work_experience_id IN (
          SELECT id FROM public.work_experience WHERE user_id = auth.uid()
        )
      );
  END IF;
END $$;

-- ------------------------------------------------------------
-- Trigger function: update_updated_at_column()
-- What: Shared trigger function to keep updated_at current on UPDATE.
-- Why: Prevents application code from needing to manage timestamps consistently.
-- ------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;

-- What: Attach updated_at triggers to tables that have updated_at.
-- Why: Ensures updated_at is correct for all writes regardless of client code path.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger WHERE tgname = 'trg_user_profiles_updated_at'
  ) THEN
    CREATE TRIGGER trg_user_profiles_updated_at
    BEFORE UPDATE ON public.user_profiles
    FOR EACH ROW
    EXECUTE FUNCTION public.update_updated_at_column();
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger WHERE tgname = 'trg_user_skills_updated_at'
  ) THEN
    CREATE TRIGGER trg_user_skills_updated_at
    BEFORE UPDATE ON public.user_skills
    FOR EACH ROW
    EXECUTE FUNCTION public.update_updated_at_column();
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger WHERE tgname = 'trg_work_experience_updated_at'
  ) THEN
    CREATE TRIGGER trg_work_experience_updated_at
    BEFORE UPDATE ON public.work_experience
    FOR EACH ROW
    EXECUTE FUNCTION public.update_updated_at_column();
  END IF;
END $$;

-- ------------------------------------------------------------
-- Seed data: skills (~51 rows)
-- What: Pre-populates the canonical skills catalog used across the product.
-- Why: Provides stable, shareable identifiers and a usable starting taxonomy.
-- ------------------------------------------------------------

-- Step 1: Insert top-level skills (parent_skill_id = NULL).
INSERT INTO public.skills (name, display_name, category, parent_skill_id)
VALUES
  ('python', 'Python', 'language', NULL),
  ('sql', 'SQL', 'language', NULL),
  ('dax', 'DAX', 'language', NULL),
  ('javascript', 'JavaScript', 'language', NULL),
  ('r', 'R', 'language', NULL),
  ('dbt', 'dbt', 'framework', NULL),
  ('pandas', 'Pandas', 'framework', NULL),
  ('spark', 'Apache Spark', 'framework', NULL),
  ('airflow', 'Apache Airflow', 'framework', NULL),
  ('streamlit', 'Streamlit', 'framework', NULL),
  ('react', 'React', 'framework', NULL),
  ('power_bi', 'Power BI', 'tool', NULL),
  ('tableau', 'Tableau', 'tool', NULL),
  ('git', 'Git', 'tool', NULL),
  ('github_actions', 'GitHub Actions', 'tool', NULL),
  ('cursor', 'Cursor AI', 'tool', NULL),
  ('vs_code', 'VS Code', 'tool', NULL),
  ('docker', 'Docker', 'tool', NULL),
  ('supabase', 'Supabase', 'platform', NULL),
  ('postgresql', 'PostgreSQL', 'platform', NULL),
  ('snowflake', 'Snowflake', 'platform', NULL),
  ('bigquery', 'BigQuery', 'platform', NULL),
  ('databricks', 'Databricks', 'platform', NULL),
  ('aws', 'AWS', 'platform', NULL),
  ('azure', 'Azure', 'platform', NULL),
  ('gcp', 'Google Cloud', 'platform', NULL),
  ('data_modeling', 'Data Modeling', 'concept', NULL),
  ('etl_design', 'ETL Design', 'concept', NULL),
  ('data_governance', 'Data Governance', 'concept', NULL),
  ('testing', 'Testing', 'concept', NULL),
  ('ci_cd', 'CI/CD', 'concept', NULL),
  ('api_integration', 'API Integration', 'concept', NULL),
  ('prompt_engineering', 'Prompt Engineering', 'concept', NULL),
  ('rag', 'RAG (Retrieval-Augmented Generation)', 'concept', NULL),
  ('llm_integration', 'LLM Integration', 'concept', NULL),
  ('data_pipelines', 'Data Pipelines', 'concept', NULL),
  ('version_control', 'Version Control', 'concept', NULL),
  ('stakeholder_communication', 'Stakeholder Communication', 'soft_skill', NULL),
  ('documentation', 'Documentation', 'soft_skill', NULL),
  ('project_management', 'Project Management', 'soft_skill', NULL)
ON CONFLICT (name) DO UPDATE
SET
  display_name = EXCLUDED.display_name,
  category = EXCLUDED.category,
  parent_skill_id = EXCLUDED.parent_skill_id;

-- Step 2: Insert child skills by resolving parent_skill_id from parent names.
WITH child_rows AS (
  SELECT *
  FROM (
    VALUES
      ('python_testing', 'Python Testing (pytest)', 'concept', 'python'),
      ('python_apis', 'Python API Development', 'concept', 'python'),
      ('python_scripting', 'Python Scripting', 'concept', 'python'),
      ('window_functions', 'Window Functions', 'concept', 'sql'),
      ('ctes', 'Common Table Expressions', 'concept', 'sql'),
      ('query_optimization', 'Query Optimization', 'concept', 'sql'),
      ('stored_procedures', 'Stored Procedures', 'concept', 'sql'),
      ('dbt_staging', 'dbt Staging Models', 'concept', 'dbt'),
      ('dbt_testing', 'dbt Testing', 'concept', 'dbt'),
      ('dbt_macros', 'dbt Macros', 'concept', 'dbt'),
      ('dbt_documentation', 'dbt Documentation', 'concept', 'dbt')
  ) AS v(name, display_name, category, parent_name)
),
parents AS (
  SELECT s.name, s.id
  FROM public.skills s
  WHERE s.name IN ('python', 'sql', 'dbt')
)
INSERT INTO public.skills (name, display_name, category, parent_skill_id)
SELECT c.name, c.display_name, c.category, p.id
FROM child_rows c
JOIN parents p ON p.name = c.parent_name
ON CONFLICT (name) DO UPDATE
SET
  display_name = EXCLUDED.display_name,
  category = EXCLUDED.category,
  parent_skill_id = EXCLUDED.parent_skill_id;

-- ------------------------------------------------------------
-- Verification queries (manual): list all Module 1 tables + row counts
-- What: Quick sanity checks after running the migration.
-- Why: Confirms objects exist and seed data loaded as expected.
-- ------------------------------------------------------------
-- skills
-- SELECT COUNT(*) AS skills_count FROM public.skills;
-- user_profiles
-- SELECT COUNT(*) AS user_profiles_count FROM public.user_profiles;
-- user_target_roles
-- SELECT COUNT(*) AS user_target_roles_count FROM public.user_target_roles;
-- user_skills
-- SELECT COUNT(*) AS user_skills_count FROM public.user_skills;
-- work_experience
-- SELECT COUNT(*) AS work_experience_count FROM public.work_experience;
-- work_experience_skills
-- SELECT COUNT(*) AS work_experience_skills_count FROM public.work_experience_skills;

-- ============================================================
-- To rollback, run the DOWN section below:
-- DOWN: Drop everything in reverse dependency order
-- Why: Ensures clean teardown without FK dependency errors.
-- ============================================================
-- DROP TABLE IF EXISTS public.work_experience_skills;
-- DROP TABLE IF EXISTS public.work_experience;
-- DROP TABLE IF EXISTS public.user_skills;
-- DROP TABLE IF EXISTS public.user_target_roles;
-- DROP TABLE IF EXISTS public.user_profiles;
-- DROP TABLE IF EXISTS public.skills;
-- DROP FUNCTION IF EXISTS public.update_updated_at_column();
