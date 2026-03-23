-- ============================================================
-- Migration 006: Learning Lab tables
-- Adds: curriculum_topics, questions_bank, study_sessions,
--        assessment_results, curriculum_progress, topic_skill_mapping
-- ============================================================

-- UP

-- Curriculum topics - the 20 DE Learning Lab topics + custom ones
CREATE TABLE IF NOT EXISTS public.curriculum_topics (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  topic_number smallint NOT NULL,          -- 1-20 for standard, 100+ for custom
  title text NOT NULL,                     -- "SELECT Fundamentals"
  category text NOT NULL CHECK (category IN ('sql', 'python', 'dbt', 'de_concepts')),
  description text,                        -- Brief description of what this topic covers
  is_custom boolean NOT NULL DEFAULT false, -- true for user-added topics
  created_at timestamptz NOT NULL DEFAULT now()
);

-- Questions bank - pre-seeded questions for practice and assessment
CREATE TABLE IF NOT EXISTS public.questions_bank (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  topic_id uuid NOT NULL REFERENCES public.curriculum_topics(id) ON DELETE CASCADE,
  difficulty smallint NOT NULL CHECK (difficulty BETWEEN 1 AND 3),  -- 1=easy, 2=medium, 3=hard
  question_type text NOT NULL CHECK (question_type IN ('write_query', 'predict_output', 'find_bug', 'conceptual', 'scenario')),
  question_text text NOT NULL,             -- The question shown to the user
  sample_data text,                        -- Optional: table schema / sample data for context
  expected_answer text NOT NULL,           -- The correct answer (used by Claude for grading)
  hints text,                              -- Optional hints (shown if user struggles)
  created_at timestamptz NOT NULL DEFAULT now()
);

-- Study sessions - logged time spent learning
CREATE TABLE IF NOT EXISTS public.study_sessions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  topic_id uuid NOT NULL REFERENCES public.curriculum_topics(id) ON DELETE CASCADE,
  mode text NOT NULL CHECK (mode IN ('learn', 'practice', 'assess')),
  duration_minutes smallint,
  notes text,
  started_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz
);

-- Assessment results - individual question answers within a session
CREATE TABLE IF NOT EXISTS public.assessment_results (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  session_id uuid NOT NULL REFERENCES public.study_sessions(id) ON DELETE CASCADE,
  question_id uuid NOT NULL REFERENCES public.questions_bank(id) ON DELETE CASCADE,
  user_answer text NOT NULL,
  is_correct boolean,                      -- Set by Claude API feedback
  feedback text,                           -- Claude's personalized feedback
  answered_at timestamptz NOT NULL DEFAULT now()
);

-- Curriculum progress - aggregated progress per topic per user
CREATE TABLE IF NOT EXISTS public.curriculum_progress (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  topic_id uuid NOT NULL REFERENCES public.curriculum_topics(id) ON DELETE CASCADE,
  status text NOT NULL DEFAULT 'not_started' CHECK (status IN ('not_started', 'in_progress', 'assessed')),
  best_score smallint,                     -- Best assessment score (0-5)
  attempts smallint NOT NULL DEFAULT 0,
  last_studied_at timestamptz,
  UNIQUE (user_id, topic_id)
);

-- Topic-to-skill mapping - connects Learning Lab topics to DataPulse skills
CREATE TABLE IF NOT EXISTS public.topic_skill_mapping (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  topic_id uuid NOT NULL REFERENCES public.curriculum_topics(id) ON DELETE CASCADE,
  skill_id uuid NOT NULL REFERENCES public.skills(id) ON DELETE CASCADE,
  UNIQUE (topic_id, skill_id)
);

-- RLS policies
ALTER TABLE public.curriculum_topics ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.questions_bank ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.study_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.assessment_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.curriculum_progress ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.topic_skill_mapping ENABLE ROW LEVEL SECURITY;

-- curriculum_topics and questions_bank: readable by all authenticated users (reference data)
CREATE POLICY "Authenticated users can read topics" ON public.curriculum_topics
  FOR SELECT TO authenticated USING (true);

CREATE POLICY "Authenticated users can read questions" ON public.questions_bank
  FOR SELECT TO authenticated USING (true);

-- topic_skill_mapping: readable by all authenticated users
CREATE POLICY "Authenticated users can read topic-skill mappings" ON public.topic_skill_mapping
  FOR SELECT TO authenticated USING (true);

-- study_sessions: users can only CRUD their own
CREATE POLICY "Users manage own study sessions" ON public.study_sessions
  FOR ALL TO authenticated USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

-- assessment_results: users can only CRUD their own
CREATE POLICY "Users manage own assessment results" ON public.assessment_results
  FOR ALL TO authenticated USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

-- curriculum_progress: users can only CRUD their own
CREATE POLICY "Users manage own curriculum progress" ON public.curriculum_progress
  FOR ALL TO authenticated USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

-- Seed the 20 standard curriculum topics
INSERT INTO public.curriculum_topics (topic_number, title, category, description) VALUES
  (1, 'SELECT Fundamentals', 'sql', 'Filtering, sorting, aliases, DISTINCT, LIMIT, NULL handling'),
  (2, 'JOINs', 'sql', 'INNER, LEFT, RIGHT, FULL, CROSS, self-joins, multi-condition joins'),
  (3, 'GROUP BY & Aggregation', 'sql', 'COUNT, SUM, AVG, HAVING, WHERE vs HAVING'),
  (4, 'Subqueries & CTEs', 'sql', 'Scalar/list/EXISTS subqueries, WITH clause, recursive CTEs'),
  (5, 'Window Functions', 'sql', 'ROW_NUMBER, RANK, LAG/LEAD, running totals, frame specs'),
  (6, 'Data Modification', 'sql', 'INSERT, UPDATE, DELETE, UPSERT, transactions'),
  (7, 'DDL & Data Modeling', 'sql', 'CREATE TABLE, constraints, indexes, normalization'),
  (8, 'Advanced DE Patterns', 'sql', 'Deduplication, SCD, gap-and-island, EXPLAIN ANALYZE'),
  (9, 'Python Fundamentals', 'python', 'Types, functions, control flow, comprehensions, file I/O'),
  (10, 'Error Handling & Modules', 'python', 'try/except, custom exceptions, imports, packages'),
  (11, 'APIs & HTTP', 'python', 'requests library, JSON, pagination, rate limiting, auth'),
  (12, 'Databases from Python', 'python', 'psycopg2, Supabase client, parameterized queries'),
  (13, 'pandas Basics', 'python', 'Read, filter, aggregate, merge, write'),
  (14, 'Testing', 'python', 'pytest, fixtures, mocking, test-driven development basics'),
  (15, 'dbt Core Concepts', 'dbt', 'Models, sources, ref(), materializations'),
  (16, 'dbt Testing & Docs', 'dbt', 'Schema tests, custom tests, dbt docs generate'),
  (17, 'Advanced dbt', 'dbt', 'Jinja, macros, packages, incremental models, snapshots'),
  (18, 'Data Engineering Lifecycle', 'de_concepts', 'Reis/Housley framework, ingestion to serving'),
  (19, 'Data Modeling Theory', 'de_concepts', 'Star schema, snowflake, SCDs, Kimball methodology'),
  (20, 'Pipeline Architecture', 'de_concepts', 'Batch vs streaming, idempotency, orchestration, DAGs')
ON CONFLICT DO NOTHING;

-- DOWN (commented out)
-- DROP TABLE IF EXISTS public.topic_skill_mapping;
-- DROP TABLE IF EXISTS public.curriculum_progress;
-- DROP TABLE IF EXISTS public.assessment_results;
-- DROP TABLE IF EXISTS public.study_sessions;
-- DROP TABLE IF EXISTS public.questions_bank;
-- DROP TABLE IF EXISTS public.curriculum_topics;
