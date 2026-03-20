-- ============================================================
-- DataPulse Module 2 Phase 1: Market Intelligence — Schema Migration
-- Migration: 003_module2_market_intelligence.sql
-- Date: 2026-03-20
-- Description: Shared RSS feed storage (feed_items) and Claude-extracted
--   signals (market_signals) for the Market Intelligence Agent.
-- ============================================================

-- UP: Create tables, indexes, RLS policies.
-- Why: Raw ingestion and extracted intelligence are global (no user_id);
--   all authenticated users read the same corpus; the Python pipeline uses
--   the service role key and bypasses RLS for writes.

-- ------------------------------------------------------------
-- Table 1/2: feed_items
-- What: One row per article ingested from configured RSS sources.
-- Why: Central dedupe (UNIQUE url) and queue (is_processed) before Claude
--   extraction; avoids per-user duplicate storage for 38 shared feeds.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.feed_items (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_key text NOT NULL,
  source_category text NOT NULL
    CHECK (
      source_category IN (
        'vendor',
        'ai_research',
        'community',
        'industry',
        'practitioner',
        'eu_regulation',
        'czech_cee'
      )
    ),
  url text NOT NULL UNIQUE,
  title text NOT NULL,
  summary text,
  author text,
  published_at timestamptz,
  fetched_at timestamptz NOT NULL DEFAULT now(),
  language text NOT NULL DEFAULT 'en',
  is_processed boolean NOT NULL DEFAULT false
);

ALTER TABLE public.feed_items ENABLE ROW LEVEL SECURITY;

-- What: Any logged-in user can read the global article feed.
-- Why: Product surfaces the same market corpus to every user; RLS still
--   blocks anonymous access.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_policies
    WHERE schemaname = 'public'
      AND tablename = 'feed_items'
      AND policyname = 'feed_items_select_authenticated'
  ) THEN
    CREATE POLICY feed_items_select_authenticated
      ON public.feed_items
      FOR SELECT
      TO authenticated
      USING (true);
  END IF;
END $$;

-- What: Authenticated users cannot insert feed rows (always false check).
-- Why: Only the ingestion job (service role) should write; normal JWT users
--   must not pollute or bypass the collector.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_policies
    WHERE schemaname = 'public'
      AND tablename = 'feed_items'
      AND policyname = 'feed_items_insert_authenticated'
  ) THEN
    CREATE POLICY feed_items_insert_authenticated
      ON public.feed_items
      FOR INSERT
      TO authenticated
      WITH CHECK (false);
  END IF;
END $$;

-- What: Authenticated users cannot update feed rows.
-- Why: Updates (e.g. is_processed) are pipeline-only operations.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_policies
    WHERE schemaname = 'public'
      AND tablename = 'feed_items'
      AND policyname = 'feed_items_update_authenticated'
  ) THEN
    CREATE POLICY feed_items_update_authenticated
      ON public.feed_items
      FOR UPDATE
      TO authenticated
      USING (false)
      WITH CHECK (false);
  END IF;
END $$;

-- Note: No DELETE policy for authenticated on feed_items.
-- Why: With RLS enabled and no DELETE policy for a role, DELETE is denied;
--   service role bypasses RLS for operational maintenance if needed.

-- ------------------------------------------------------------
-- Table 2/2: market_signals
-- What: Structured signals extracted from a single feed item by Claude.
-- Why: Normalizes AI output for joins to skills and downstream dbt models;
--   optional skill_id links to taxonomy when extraction maps cleanly.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.market_signals (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  feed_item_id uuid NOT NULL
    REFERENCES public.feed_items(id) ON DELETE CASCADE,
  skill_id uuid NULL REFERENCES public.skills(id) ON DELETE SET NULL,
  skill_name_raw text NOT NULL,
  signal_type text NOT NULL
    CHECK (
      signal_type IN (
        'skill_demand',
        'tool_adoption',
        'trend_emerging',
        'trend_declining',
        'regulatory_update'
      )
    ),
  strength smallint NOT NULL CHECK (strength BETWEEN 1 AND 5),
  confidence smallint NOT NULL CHECK (confidence BETWEEN 1 AND 5),
  region text NOT NULL DEFAULT 'global',
  summary text NOT NULL,
  extracted_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.market_signals ENABLE ROW LEVEL SECURITY;

-- What: Any logged-in user can read extracted signals.
-- Why: Signals are global intelligence layered on global feed_items;
--   personalization happens in Module 3 via joins to user_skills.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_policies
    WHERE schemaname = 'public'
      AND tablename = 'market_signals'
      AND policyname = 'market_signals_select_authenticated'
  ) THEN
    CREATE POLICY market_signals_select_authenticated
      ON public.market_signals
      FOR SELECT
      TO authenticated
      USING (true);
  END IF;
END $$;

-- What: Authenticated users cannot insert signals.
-- Why: Only the Claude pipeline (service role) creates rows after extraction.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_policies
    WHERE schemaname = 'public'
      AND tablename = 'market_signals'
      AND policyname = 'market_signals_insert_authenticated'
  ) THEN
    CREATE POLICY market_signals_insert_authenticated
      ON public.market_signals
      FOR INSERT
      TO authenticated
      WITH CHECK (false);
  END IF;
END $$;

-- What: Authenticated users cannot update signals.
-- Why: Immutability after extraction avoids tampering; corrections are
--   service-role maintenance if ever needed.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_policies
    WHERE schemaname = 'public'
      AND tablename = 'market_signals'
      AND policyname = 'market_signals_update_authenticated'
  ) THEN
    CREATE POLICY market_signals_update_authenticated
      ON public.market_signals
      FOR UPDATE
      TO authenticated
      USING (false)
      WITH CHECK (false);
  END IF;
END $$;

-- What: Authenticated users cannot delete signals.
-- Why: Deletes are reserved for the service role (e.g. reprocessing).
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_policies
    WHERE schemaname = 'public'
      AND tablename = 'market_signals'
      AND policyname = 'market_signals_delete_authenticated'
  ) THEN
    CREATE POLICY market_signals_delete_authenticated
      ON public.market_signals
      FOR DELETE
      TO authenticated
      USING (false);
  END IF;
END $$;

-- ------------------------------------------------------------
-- Indexes: feed_items
-- What: Partial/column indexes to match collector and analytics access paths.
-- Why: Unprocessed scans, time-window filters, and category slicers must stay
--   cheap as the corpus grows.
-- ------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_feed_items_is_processed
  ON public.feed_items (is_processed);

CREATE INDEX IF NOT EXISTS idx_feed_items_published_at
  ON public.feed_items (published_at);

CREATE INDEX IF NOT EXISTS idx_feed_items_source_category
  ON public.feed_items (source_category);

-- ------------------------------------------------------------
-- Indexes: market_signals
-- What: JOIN and filter columns plus a covering composite for Module 3 dbt.
-- Why: skill_id joins to skills, signal_type filters trends, extracted_at
--   bounds time ranges; composite aligns with common multi-column predicates.
-- ------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_market_signals_skill_id
  ON public.market_signals (skill_id);

CREATE INDEX IF NOT EXISTS idx_market_signals_signal_type
  ON public.market_signals (signal_type);

CREATE INDEX IF NOT EXISTS idx_market_signals_extracted_at
  ON public.market_signals (extracted_at);

CREATE INDEX IF NOT EXISTS idx_market_signals_skill_type_extracted
  ON public.market_signals (skill_id, signal_type, extracted_at);

-- ------------------------------------------------------------
-- Verification
-- What: Confirms both tables exist and reports row counts after migration.
-- Why: Running these immediately validates object creation (0 rows on first apply).
-- ------------------------------------------------------------
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN ('feed_items', 'market_signals')
ORDER BY table_name;

SELECT COUNT(*) AS feed_items_count FROM public.feed_items;
SELECT COUNT(*) AS market_signals_count FROM public.market_signals;

-- ============================================================
-- DOWN: Rollback (commented — run manually in reverse dependency order)
-- Why: market_signals references feed_items; drop child first to satisfy FKs.
-- ============================================================
-- DROP TABLE IF EXISTS public.market_signals;
-- DROP TABLE IF EXISTS public.feed_items;
