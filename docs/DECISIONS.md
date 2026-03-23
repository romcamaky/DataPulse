# DataPulse — Decision Log

Append-only. Every architectural or product decision gets logged here with date, decision, reasoning, and who decided.

---

## 2026-03-17 | Product direction

**Decision:** Transform the learning tracker project into DataPulse — a personal AI career intelligence platform.

**Why:** A product that profiles skills, monitors market trends, and generates personalized recommendations is a significantly stronger portfolio signal than a learning session tracker. One product with 5 modules replaces 5 isolated artifacts. Shows system thinking.

**Decided by:** Romi + Prompt Architect

---

## 2026-03-17 | Tech stack — what we use

**Decision:** Supabase (PostgreSQL + Auth + RLS), dbt Core, Python, Claude API, GitHub Actions, Cursor, Lovable → later Streamlit/React.

**Why:** Builds on existing infrastructure. No unnecessary complexity. Every tool earns its place.

**Decided by:** Romi + Prompt Architect

---

## 2026-03-17 | Tech stack — what we don't use

**Decision:** No LangChain, no CrewAI, no FastAPI, no Airflow, no job board scraping.

**Why:** LangChain/CrewAI add abstraction without value for our scope — plain Python + Claude API is simpler, cheaper, and explainable. FastAPI is unnecessary because Supabase IS the backend. Airflow is overkill — GitHub Actions cron handles our scheduling. Job board scraping is legally risky and technically fragile — RSS feeds are stable and legal.

**Decided by:** Romi + Prompt Architect

---

## 2026-03-17 | Repo strategy

**Decision:** New repo for DataPulse. Shared Supabase instance with existing project.

**Why:** DataPulse is a product; the learning journey repo is a learning log. Two separate GitHub stories for recruiters. But same PostgreSQL database — DataPulse tables live alongside existing 8 tables.

**Decided by:** Romi + CTO

---

## 2026-03-17 | Existing table overlap

**Decision:** Start clean with new DataPulse tables. No migration from existing `knowledge_tracking`, `sessions`, or `tutor_sessions`.

**Why:** Don't couple new product to legacy schema decisions. But design new tables with forward-compatible column types so historical data import is possible later.

**Decided by:** Romi (CTO proposed options, Romi chose clean start)

---

## 2026-03-17 | Skills taxonomy

**Decision:** Canonical `skills` reference table with hierarchical structure (`parent_skill_id`, self-referencing FK). Seed with ~50 skills. Both `user_skills` and `market_signals` reference this table.

**Why:** Without normalization, "Python" vs "python" vs "Python 3" breaks the skill gap join in Module 3. Hierarchy needed because market signals reference both general ("Python") and specific ("Pandas") levels.

**Decided by:** CTO proposed canonical table, Romi added hierarchy requirement

---

## 2026-03-17 | user_profiles field scope

**Decision:** Fields include: core (name, email, bio, career_narrative), current state (role, company, size, industry, years), location (country, city, timezone, remote_preference), learning (weekly_hours, learning_preferences). Target roles in separate `user_target_roles` table.

**Why:** Every field feeds the recommendation engine. `career_narrative` (free text) lets Claude API extract context that structured fields miss. Multiple target roles needed because users may target 2–4 roles simultaneously.

**Decided by:** CTO proposed base fields, Romi added career_narrative and multi-target-role design

---

## 2026-03-17 | Build order

**Decision:** 5 modules built sequentially: Profile Engine → Market Agent → Skill Gap Analyzer → Learning Path Updater → Multi-User App. Each module maps to specific curriculum topics.

**Why:** Build order follows Romi's learning curriculum. Module 1 needs Python basics (Topics 9–10), Module 2 needs APIs (Topics 11–12), etc. Never build what you can't explain.

**Decided by:** Romi + Prompt Architect

---

## 2026-03-17 | Automation principles

**Decision:** Every recurring task must have a CLI command, cron job, or webhook. Weekly pipeline runs with zero human input. User interaction limited to reading reports and approving/rejecting recommendations.

**Why:** 3–4 hours/week budget means every minute of manual work is expensive. Copy-paste between systems is a design failure.

**Decided by:** Romi + Prompt Architect

---

## 2026-03-17 | Reserved word: current_role → role_title

**Decision:** Renamed `user_profiles.current_role` to `role_title`.

**Why:** `current_role` is a reserved word in PostgreSQL (system function returning the active role name). Using it as a column name requires quoting everywhere — dbt models, Python queries, CLI. Renaming to `role_title` avoids this and matches `work_experience.role_title` pattern.

**Decided by:** CTO caught the error, Romi approved rename

---

## 2026-03-17 | Junction table over UUID array

**Decision:** `work_experience_skills` junction table instead of `skill_ids uuid[]` on `work_experience`.

**Why:** Three reasons: (1) Module 3 joins user skills from work experience against market signals — junction table gives clean JOINs vs unnest() on every query. (2) FK enforcement — arrays can't enforce referential integrity. (3) Portfolio signal — proper relational modeling in a public repo.

**Decided by:** Romi decided, CTO proposed both options

---

## 2026-03-20 | Module 2 schema — shared feed_items and market_signals

**Decision:** feed_items and market_signals tables have NO user_id column. They are shared/global data.

**Why:** All users consume the same 38 RSS feeds. Storing per-user duplicates wastes space and complicates deduplication. The personalization happens in Module 3 where dbt models JOIN market_signals (global) against user_skills (per-user) to produce individualized gap analysis. RLS allows all authenticated users to read; only the service role pipeline can write.

**Also decided:** Added `confidence` column (1-5) on market_signals so Claude rates its extraction certainty. Costs zero extra tokens, enables Module 3 to filter low-confidence noise (WHERE confidence >= 3).

**Decided by:** Romi + CTO


## 2026-03-20 | Access control — invite-only registration

**Decision:** DataPulse will use invite-only registration. Only whitelisted email addresses can sign up. No open self-registration.

**Why:** The public GitHub repo exposes the codebase but not the infrastructure. However, once Module 5 adds a web frontend with Supabase Auth, open registration would let strangers trigger Claude API calls at the owner's expense. Invite-only (whitelist of allowed emails checked at signup) eliminates this risk. Current whitelist: Romi + Petr. Expanding later is a one-row insert.

**Implementation (Module 5):** Supabase Auth + an `allowed_emails` table or Auth hook that rejects non-whitelisted signups. Exact mechanism TBD when we build Module 5.

**Decided by:** Romi + CTO


## 2026-03-20 | RSS feed config — Python dict over database table

**Decision:** Store the 31 RSS feed sources in a Python config file (`feeds_config.py`), not in a Supabase table.

**Why:** No UI to manage feeds yet (Module 5 territory). A Python dict is simpler to update, version-controlled, and doesn't need RLS. Migration to a table later is trivial.

**Decided by:** CTO recommended, Romi agreed

---

## 2026-03-20 | Signal extraction model — Haiku over Sonnet

**Decision:** Use `claude-haiku-4-5-20251001` for market signal extraction, not Sonnet.

**Why:** Signal extraction is structured data extraction (JSON output from article titles + summaries). Haiku is 3x cheaper and fast enough. Sonnet is reserved for Module 3 personalized recommendations where reasoning quality matters more.

**Decided by:** CTO recommended, Romi agreed

---

## 2026-03-20 | Pipeline frequency — biweekly over weekly

**Decision:** RSS collection + signal extraction runs every two weeks, not weekly.

**Why:** For 1-2 users, career intelligence signals don't change week-to-week. Biweekly halves API cost and produces reports with more accumulated signal. Can switch to weekly with a one-line cron change if reports feel stale.

**Decided by:** Romi decided after cost discussion with CTO


## 2026-03-22 | Recommender RLS — INSERT restricted to service role

**Decision:** `authenticated` role has INSERT denied (`WITH CHECK (false)`) on `recommendations`. Only the service role (used by the Python pipeline) can write recommendations.

**Why:** Same pattern as `market_signals`. The recommender runs as a backend pipeline, not as an authenticated user. Allowing authenticated INSERT would open a privilege escalation vector in a multi-user app. Service role bypasses RLS by design — this is the correct Supabase pattern for server-side writes.

**Decided by:** Cursor (proposed), CTO (approved)

---

## 2026-03-22 | Recommender prompt — framework exclusion list

**Decision:** Recommender prompt must explicitly instruct Claude not to recommend LangChain, CrewAI, FastAPI, or Airflow as learning resources or tools.

**Why:** These are excluded from the DataPulse tech stack by design (see 2026-03-17 decision). A recommendation to "learn LangChain" contradicts the architectural decisions already logged and would confuse the user. The model has no awareness of project-level constraints unless explicitly told.

**Implementation:** Add a constraints block to the recommender system prompt: "Do not recommend the following tools: LangChain, CrewAI, FastAPI, Airflow. Prefer simpler alternatives that achieve the same outcome."

**Decided by:** CTO observed in Module 3 output, Romi approved


## 2026-03-22 | Module 4 scope — defer tests and approve/reject CLI

**Decision:** Ship Module 4 without the pytest suite and approve/reject CLI.
Both are deferred until the user profile is updated with real, complete data.

**Why:** Tests written against sparse profile data lock in incomplete behavior.
The approve/reject CLI only matters once recommendations are being acted on
regularly. Neither omission blocks the pipeline or the portfolio story.

**Deferred to:** Before Module 5 ships.

**Decided by:** Romi

---

## 2026-03-22 | system-overview.md as living architecture document

**Decision:** `docs/architecture/system-overview.md` is the single source of
truth for system architecture. It must be updated whenever a new module ships
or a significant architectural change is made.

**Why:** Recruiters and interviewers read docs, not code. A maintained
architecture document with a rendered Mermaid diagram is a stronger portfolio
signal than comments scattered across files.

**Decided by:** Romi + CTO

---

## 2026-03-23 | Learning Lab schema alignment

**Decision:** Use actual migration schema for assessment_results and
curriculum_progress instead of prompt spec columns.

**Why:** assessment_results requires session_id (FK), not topic_id directly.
curriculum_progress uses best_score + attempts, not score_percentage.
Fallback logic was removed in favor of single correct code path.

**Decided by:** CTO (schema mismatch caught before runtime)

---

## 2026-03-23 | topic_skill_mapping seed

**Decision:** Map Topics 1-5 to sql, query_optimization, ctes,
window_functions skills only.

**Why:** These are the skills directly practiced in SQL topics.
Broader skill inference deferred to Module 3 gap analysis.

**Decided by:** CTO