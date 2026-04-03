-- Migration 008: Study Documentation
-- Purpose: Per-user, per-topic study notes generated after each Lab session.
-- Structure is human-readable markdown, also used as Claude context in future sessions.

CREATE TABLE study_documentation (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    topic_id uuid NOT NULL REFERENCES curriculum_topics(id) ON DELETE CASCADE,
    content text NOT NULL,              -- full markdown document for this topic
    last_updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, topic_id)          -- one document per user per topic, updated in place
);

ALTER TABLE study_documentation ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users manage own study documentation"
    ON study_documentation
    FOR ALL
    TO authenticated
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);
