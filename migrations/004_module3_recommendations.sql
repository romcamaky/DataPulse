-- ============================================================
-- DataPulse Module 3 Phase 3: Personalized Recommendations
-- Migration: 004_module3_recommendations.sql
-- Date: 2026-03-22
-- Description: Stores Claude-generated learning recommendations per user;
--   batch_id groups rows from one generation run; pending rows are replaced
--   on each run while approved/rejected/completed are retained.
-- ============================================================

-- UP

-- Align user_target_roles with dbt staging (timeline, market_scope) if missing.
ALTER TABLE public.user_target_roles
  ADD COLUMN IF NOT EXISTS timeline text;

ALTER TABLE public.user_target_roles
  ADD COLUMN IF NOT EXISTS market_scope text;

-- ------------------------------------------------------------
-- Table: recommendations
-- What: One row per suggested learning action tied to a skill gap (optional FK).
-- Why: Renders a personalized backlog; status workflow supports user curation.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.recommendations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  skill_id uuid REFERENCES public.skills(id) ON DELETE SET NULL,
  gap_rank smallint,
  priority_tier text
    CHECK (priority_tier IN ('critical', 'important', 'nice_to_have')),
  recommendation_text text NOT NULL,
  resource_type text
    CHECK (
      resource_type IN (
        'course',
        'tutorial',
        'project',
        'book',
        'podcast',
        'documentation',
        'practice',
        'certification'
      )
    ),
  resource_url text,
  estimated_hours smallint,
  status text NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'approved', 'rejected', 'completed')),
  generated_at timestamptz NOT NULL DEFAULT now(),
  reviewed_at timestamptz,
  batch_id text NOT NULL
);

COMMENT ON COLUMN public.recommendations.batch_id IS
  'Groups recommendations from the same generation run (e.g. date + user id prefix).';

CREATE INDEX IF NOT EXISTS idx_recommendations_user_status
  ON public.recommendations (user_id, status);

CREATE INDEX IF NOT EXISTS idx_recommendations_batch
  ON public.recommendations (batch_id);

ALTER TABLE public.recommendations ENABLE ROW LEVEL SECURITY;

-- What: Users read only their own recommendations.
-- Why: Tenant isolation for personalized learning backlog.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_policies
    WHERE schemaname = 'public'
      AND tablename = 'recommendations'
      AND policyname = 'Users can view own recommendations'
  ) THEN
    CREATE POLICY "Users can view own recommendations"
      ON public.recommendations
      FOR SELECT
      TO authenticated
      USING (auth.uid() = user_id);
  END IF;
END $$;

-- What: Users may update their own rows (e.g. approve/reject/complete).
-- Why: Interactive workflow without service-role writes from the client.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_policies
    WHERE schemaname = 'public'
      AND tablename = 'recommendations'
      AND policyname = 'Users can update own recommendations'
  ) THEN
    CREATE POLICY "Users can update own recommendations"
      ON public.recommendations
      FOR UPDATE
      TO authenticated
      USING (auth.uid() = user_id)
      WITH CHECK (auth.uid() = user_id);
  END IF;
END $$;

-- What: End users cannot insert recommendations (pipeline uses service role).
-- Why: Prevents forged rows; keeps generation under server-side control.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_policies
    WHERE schemaname = 'public'
      AND tablename = 'recommendations'
      AND policyname = 'recommendations_insert_authenticated'
  ) THEN
    CREATE POLICY recommendations_insert_authenticated
      ON public.recommendations
      FOR INSERT
      TO authenticated
      WITH CHECK (false);
  END IF;
END $$;

-- Note: Batch inserts use the Supabase service role key, which bypasses RLS.
-- Authenticated clients cannot INSERT rows (WITH CHECK false); this avoids a
-- wide-open INSERT policy that would let any logged-in user create arbitrary rows.

-- ------------------------------------------------------------
-- Verification
-- ------------------------------------------------------------
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name = 'recommendations';

-- ============================================================
-- DOWN (commented — run manually if rolling back this migration)
-- ============================================================
-- DROP TABLE IF EXISTS public.recommendations CASCADE;
