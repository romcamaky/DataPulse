-- ============================================================
-- Migration 012: Reliable user-generated questions_bank inserts
-- Date: 2026-05-15
-- Description: Default created_by to auth.uid() and add an RPC so
--   inserts succeed when the JWT is present (auth.uid() set) without
--   relying on client-supplied created_by matching PostgREST RLS edge
--   cases. Function runs as SECURITY INVOKER (RLS applies).
-- ============================================================

BEGIN;

ALTER TABLE public.questions_bank
    ALTER COLUMN created_by SET DEFAULT auth.uid();

CREATE OR REPLACE FUNCTION public.insert_questions_bank_question(
    p_topic_id uuid,
    p_question_type text,
    p_difficulty smallint,
    p_question_text text,
    p_sample_data text,
    p_expected_answer text,
    p_hints text
)
RETURNS uuid
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public
AS $$
DECLARE
    v_uid uuid := auth.uid();
    v_id uuid;
BEGIN
    IF v_uid IS NULL THEN
        RAISE EXCEPTION 'Not authenticated'
            USING ERRCODE = '42501';
    END IF;

    INSERT INTO public.questions_bank (
        topic_id,
        question_type,
        difficulty,
        question_text,
        sample_data,
        expected_answer,
        hints,
        created_by
    ) VALUES (
        p_topic_id,
        p_question_type,
        p_difficulty,
        p_question_text,
        p_sample_data,
        p_expected_answer,
        p_hints,
        v_uid
    )
    RETURNING id INTO v_id;

    RETURN v_id;
END;
$$;

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
