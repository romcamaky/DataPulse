-- ============================================================
-- DataPulse Module 1: Onboarding Extras — Schema Migration
-- Migration: 002_onboarding_extras.sql
-- Date: 2026-03-17
-- Description: Adds tables and columns needed by the onboarding
--   questionnaire that weren't in the original schema design.
-- ============================================================

-- UP

-- --------------------------------------------------------
-- New table: user_certifications
-- Separate table (not JSONB) because we need to join
-- certification skills against the skills table in Module 3
-- for evidence-based skill confidence boosting.
-- --------------------------------------------------------
CREATE TABLE user_certifications (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    name text NOT NULL,
    provider text,
    year_completed integer,
    certificate_url text,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

-- Junction table: which skills does each certification prove?
CREATE TABLE certification_skills (
    certification_id uuid NOT NULL REFERENCES user_certifications(id) ON DELETE CASCADE,
    skill_id uuid NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    PRIMARY KEY (certification_id, skill_id)
);

-- RLS: users can only see/manage their own certifications
ALTER TABLE user_certifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE certification_skills ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own certifications"
    ON user_certifications FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own certifications"
    ON user_certifications FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own certifications"
    ON user_certifications FOR UPDATE
    USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own certifications"
    ON user_certifications FOR DELETE
    USING (auth.uid() = user_id);

CREATE POLICY "Users can view own certification skills"
    ON certification_skills FOR SELECT
    USING (certification_id IN (
        SELECT id FROM user_certifications WHERE user_id = auth.uid()
    ));

CREATE POLICY "Users can insert own certification skills"
    ON certification_skills FOR INSERT
    WITH CHECK (certification_id IN (
        SELECT id FROM user_certifications WHERE user_id = auth.uid()
    ));

CREATE POLICY "Users can delete own certification skills"
    ON certification_skills FOR DELETE
    USING (certification_id IN (
        SELECT id FROM user_certifications WHERE user_id = auth.uid()
    ));

-- Reuse existing trigger function from migration 001
CREATE TRIGGER update_user_certifications_updated_at
    BEFORE UPDATE ON user_certifications
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- --------------------------------------------------------
-- JSONB columns on user_profiles
-- Languages: display data, max 3-5 entries, no joins needed
-- Format: [{"language": "Czech", "level": "native"}, ...]
-- Platform access: simple filter for recommendation engine
-- Format: [{"platform": "Udemy", "access_type": "paid"}, ...]
-- --------------------------------------------------------
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS languages jsonb DEFAULT '[]'::jsonb;
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS platform_access jsonb DEFAULT '[]'::jsonb;

-- --------------------------------------------------------
-- Additional profile columns for questionnaire sections
-- Grouped by section for readability
-- --------------------------------------------------------

-- Section 2A: Education
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS education_level text;
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS field_of_study text;
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS thesis_description text;
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS thesis_url text;

-- Section 5: AI usage profile
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS ai_usage_frequency text;
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS ai_tools jsonb DEFAULT '[]'::jsonb;
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS ai_use_cases jsonb DEFAULT '[]'::jsonb;
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS ai_api_experience text;
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS ai_automation_level text;

-- Section 6: Learning preferences (beyond what's already on the table)
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS learning_time_preference jsonb DEFAULT '[]'::jsonb;
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS course_completion_rate text;
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS learning_failures text;

-- Section 7: Career goals (beyond what's in user_target_roles)
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS career_change_history text;
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS work_frustrations text;

-- Section 9: Portfolio links
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS github_username text;
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS linkedin_url text;
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS portfolio_url text;

-- --------------------------------------------------------
-- DOWN (commented out — run manually to rollback)
-- Drop order: junction table first, then main table, then columns
-- --------------------------------------------------------
-- DROP TABLE IF EXISTS certification_skills;
-- DROP TABLE IF EXISTS user_certifications;
-- ALTER TABLE user_profiles DROP COLUMN IF EXISTS languages;
-- ALTER TABLE user_profiles DROP COLUMN IF EXISTS platform_access;
-- ALTER TABLE user_profiles DROP COLUMN IF EXISTS education_level;
-- ALTER TABLE user_profiles DROP COLUMN IF EXISTS field_of_study;
-- ALTER TABLE user_profiles DROP COLUMN IF EXISTS thesis_description;
-- ALTER TABLE user_profiles DROP COLUMN IF EXISTS thesis_url;
-- ALTER TABLE user_profiles DROP COLUMN IF EXISTS ai_usage_frequency;
-- ALTER TABLE user_profiles DROP COLUMN IF EXISTS ai_tools;
-- ALTER TABLE user_profiles DROP COLUMN IF EXISTS ai_use_cases;
-- ALTER TABLE user_profiles DROP COLUMN IF EXISTS ai_api_experience;
-- ALTER TABLE user_profiles DROP COLUMN IF EXISTS ai_automation_level;
-- ALTER TABLE user_profiles DROP COLUMN IF EXISTS learning_time_preference;
-- ALTER TABLE user_profiles DROP COLUMN IF EXISTS course_completion_rate;
-- ALTER TABLE user_profiles DROP COLUMN IF EXISTS learning_failures;
-- ALTER TABLE user_profiles DROP COLUMN IF EXISTS career_change_history;
-- ALTER TABLE user_profiles DROP COLUMN IF EXISTS work_frustrations;
-- ALTER TABLE user_profiles DROP COLUMN IF EXISTS github_username;
-- ALTER TABLE user_profiles DROP COLUMN IF EXISTS linkedin_url;
-- ALTER TABLE user_profiles DROP COLUMN IF EXISTS portfolio_url;
