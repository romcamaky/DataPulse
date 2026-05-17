-- ============================================================
-- Migration 013: Remaining Security Advisor WARN cleanup
-- Date: 2026-05-15
-- Description:
--   - Drop pg_graphql (DataPulse uses PostgREST/REST only)
--   - Revoke authenticated SELECT on dbt/pipeline objects
--   - Harden insert_questions_bank_question (INVOKER, no anon)
--
-- Manual (not SQL): Auth → Password Security → enable leaked-password
--   protection (auth_leaked_password_protection lint).
-- ============================================================

BEGIN;

-- =====================================================================
-- Section A: Disable pg_graphql
--
-- Clears pg_graphql_authenticated_table_exposed (lint 0027) for all
-- public tables. RLS-protected app tables still need authenticated
-- SELECT for PostgREST; GraphQL introspection is not used by Streamlit.
-- =====================================================================

DROP EXTENSION IF EXISTS pg_graphql CASCADE;

-- =====================================================================
-- Section B: Revoke authenticated SELECT on internal analytics objects
--
-- Belt-and-suspenders if pg_graphql is re-enabled. Streamlit and CLI
-- use service role or marts directly; dbt staging/intermediate views
-- and raw feed_items are pipeline-only.
-- =====================================================================

REVOKE SELECT ON TABLE public.feed_items FROM authenticated;

DO $$
DECLARE
    obj text;
BEGIN
    FOREACH obj IN ARRAY ARRAY[
        'stg_feed_items',
        'stg_market_signals',
        'stg_skills',
        'stg_user_profiles',
        'stg_user_skills',
        'stg_user_target_roles',
        'int_signals_enriched',
        'int_skill_market_demand',
        'int_user_skill_coverage'
    ]
    LOOP
        IF to_regclass('public.' || obj) IS NOT NULL THEN
            EXECUTE format(
                'REVOKE SELECT ON public.%I FROM authenticated',
                obj
            );
        END IF;
    END LOOP;
END $$;

-- =====================================================================
-- Section C: insert_questions_bank_question — RPC hardening
--
-- Migration 012 left EXECUTE reachable by anon (default + PUBLIC).
-- Switch to SECURITY INVOKER so RLS applies; auth.uid() check remains.
-- =====================================================================

ALTER FUNCTION public.insert_questions_bank_question(
    uuid, text, smallint, text, text, text, text
) SECURITY INVOKER;

REVOKE ALL ON FUNCTION public.insert_questions_bank_question(
    uuid, text, smallint, text, text, text, text
) FROM PUBLIC;

REVOKE EXECUTE ON FUNCTION public.insert_questions_bank_question(
    uuid, text, smallint, text, text, text, text
) FROM anon;

GRANT EXECUTE ON FUNCTION public.insert_questions_bank_question(
    uuid, text, smallint, text, text, text, text
) TO authenticated;

COMMIT;
