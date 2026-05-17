-- ============================================================
-- Migration 011: questions_bank attribution + per-user writes
-- Date: 2026-05-15
-- Description: Add created_by column and replace migration 010
--   INSERT deny with per-user INSERT/UPDATE/DELETE policies.
-- ============================================================

BEGIN;

-- =====================================================================
-- Section A: Add created_by attribution column
--
-- Nullable: existing seeded rows (NULL = system-seeded, immutable by
-- authenticated users since the per-user policy requires created_by
-- to equal auth.uid()). New user-generated rows must set this column.
-- =====================================================================

ALTER TABLE public.questions_bank
    ADD COLUMN IF NOT EXISTS created_by uuid REFERENCES auth.users(id) ON DELETE SET NULL;

-- =====================================================================
-- Section B: Drop the deny-all INSERT policy from migration 010
-- =====================================================================

DROP POLICY IF EXISTS questions_bank_insert_deny ON public.questions_bank;

-- =====================================================================
-- Section C: Per-user INSERT — users can only insert rows attributed
-- to themselves. Service role bypasses RLS so seed scripts still work.
-- =====================================================================

DROP POLICY IF EXISTS questions_bank_insert_own ON public.questions_bank;

CREATE POLICY questions_bank_insert_own
    ON public.questions_bank
    FOR INSERT
    TO authenticated
    WITH CHECK (auth.uid() = created_by);

-- =====================================================================
-- Section D: Per-user UPDATE/DELETE — users can only modify or delete
-- their own questions. NULL created_by (system-seeded) rows cannot be
-- modified by authenticated users; only service role.
-- =====================================================================

DROP POLICY IF EXISTS questions_bank_update_own ON public.questions_bank;

CREATE POLICY questions_bank_update_own
    ON public.questions_bank
    FOR UPDATE
    TO authenticated
    USING (auth.uid() = created_by)
    WITH CHECK (auth.uid() = created_by);

DROP POLICY IF EXISTS questions_bank_delete_own ON public.questions_bank;

CREATE POLICY questions_bank_delete_own
    ON public.questions_bank
    FOR DELETE
    TO authenticated
    USING (auth.uid() = created_by);

COMMIT;
