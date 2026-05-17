-- ============================================================
-- Migration 010: Security linter WARN cleanup
-- Date: 2026-05-15
-- Description: Drop unused Journey legacy tables/views, tighten
--   questions_bank INSERT, harden update_updated_at_column,
--   revoke anon SELECT on public schema.
-- ============================================================

BEGIN;

-- =====================================================================
-- Section A: Drop unused legacy tables from AI-Native-Data-Engineer-Journey
--
-- These tables are shared in the Supabase instance from the predecessor
-- project but have ZERO references in the DataPulse codebase. Per
-- DECISIONS.md (2026-03-17), DataPulse explicitly chose not to migrate
-- this data. Dropping them resolves 8 "Allow all for authenticated"
-- RLS WARNs and removes dead schema from the database.
-- =====================================================================

DROP TABLE IF EXISTS public.artifacts CASCADE;
DROP TABLE IF EXISTS public.materials CASCADE;
DROP TABLE IF EXISTS public.sessions CASCADE;
DROP TABLE IF EXISTS public.tutor_sessions CASCADE;
DROP TABLE IF EXISTS public.knowledge_tracking CASCADE;
DROP TABLE IF EXISTS public.github_commits CASCADE;
DROP TABLE IF EXISTS public.topics CASCADE;
DROP TABLE IF EXISTS public.courses CASCADE;

-- =====================================================================
-- Section B: Drop orphan Journey dbt views
--
-- These views were created by the Journey project's dbt runs but are
-- no longer referenced by any current dbt model in dbt/models/. They
-- contributed to the GraphQL exposure warnings.
-- =====================================================================

DROP VIEW IF EXISTS public.stg_artifacts CASCADE;
DROP VIEW IF EXISTS public.stg_courses CASCADE;
DROP VIEW IF EXISTS public.stg_github_commits CASCADE;
DROP VIEW IF EXISTS public.stg_materials CASCADE;
DROP VIEW IF EXISTS public.stg_sessions CASCADE;
DROP VIEW IF EXISTS public.stg_topics CASCADE;
DROP VIEW IF EXISTS public.int_sessions_enriched CASCADE;

-- =====================================================================
-- Section C: questions_bank — admin-curated reference data
--
-- The existing "Authenticated users can insert questions" policy uses
-- WITH CHECK (true), allowing any logged-in user to insert questions
-- for any topic. questions_bank is shared reference data without a
-- created_by column. We restrict INSERT to service role only (which
-- bypasses RLS); the Learning Lab upsert in pages/2_Learning_Lab.py
-- will no longer succeed for authenticated users. If question
-- contribution becomes a feature later, it requires a schema change
-- (add created_by + per-user policy).
-- =====================================================================

DROP POLICY IF EXISTS "Authenticated users can insert questions" ON public.questions_bank;

DROP POLICY IF EXISTS questions_bank_insert_deny ON public.questions_bank;

CREATE POLICY questions_bank_insert_deny
    ON public.questions_bank
    FOR INSERT
    TO authenticated
    WITH CHECK (false);

-- =====================================================================
-- Section D: Function hardening — fix mutable search_path
--
-- Setting search_path = public prevents search_path injection attacks
-- on this trigger function. Used by triggers on user_certifications,
-- user_profiles, user_skills, work_experience.
-- =====================================================================

ALTER FUNCTION public.update_updated_at_column() SET search_path = public;

-- =====================================================================
-- Section E: Revoke SELECT from anon role on all public tables/views
--
-- Supabase defaults grant SELECT on all public objects to both 'anon'
-- and 'authenticated' roles. This exposes table schemas via
-- PostgREST/GraphQL to unauthenticated clients. DataPulse's Streamlit
-- app uses the JWT-attached authenticated client, never the bare anon
-- role for table reads (only auth API). Revoking anon SELECT closes
-- pg_graphql_anon_table_exposed linter WARNs without affecting the app.
-- =====================================================================

REVOKE SELECT ON ALL TABLES IN SCHEMA public FROM anon;

ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE SELECT ON TABLES FROM anon;

COMMIT;
