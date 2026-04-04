-- Migration 009: Theory Content
-- Purpose: Pre-seeded theoretical explanations per curriculum topic.
-- Generated once by Claude Sonnet, stored in DB, served in Learn mode.
-- Not per-user — theory is global (no user_id, no RLS needed).

CREATE TABLE theory_content (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    topic_id uuid NOT NULL REFERENCES curriculum_topics(id) ON DELETE CASCADE,
    content text NOT NULL,           -- full markdown: explanation + examples
    generated_at timestamptz NOT NULL DEFAULT now(),
    model_used text NOT NULL DEFAULT 'claude-sonnet-4-20250514',
    UNIQUE (topic_id)                -- one theory doc per topic
);

-- No RLS — theory is read-only reference data, same for all users.
-- Grant read access to authenticated users.
ALTER TABLE theory_content ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Authenticated users can read theory content"
    ON theory_content
    FOR SELECT
    TO authenticated
    USING (true);
