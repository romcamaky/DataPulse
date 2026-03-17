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
<<<<<<< HEAD

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
=======
>>>>>>> a215d9e97337a418d223751dae073fdfd6ae12b2
