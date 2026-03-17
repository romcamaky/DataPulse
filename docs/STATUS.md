# DataPulse — Current Status

**Last updated:** 2026-03-17

## Current module: 1 — Profile Engine
<<<<<<< HEAD
## Current phase: Questionnaire development
=======
## Current phase: Schema design
>>>>>>> a215d9e97337a418d223751dae073fdfd6ae12b2
## Blocked on: Nothing

---

## What's done

- [x] Product vision defined (5 modules, build order, weekly automated cycle)
- [x] Tech stack decided (Supabase, dbt, Python, Claude API, GitHub Actions, Cursor)
- [x] Repo strategy: new repo `datapulse`, shared Supabase instance
<<<<<<< HEAD
- [x] Skills taxonomy: hierarchical `skills` table with `parent_skill_id`, 51 skills seeded
- [x] `user_profiles` fields defined (core, current state, location, learning, career_narrative)
- [x] `user_target_roles` as separate table (supports multiple target roles per user)
- [x] Overlap analysis with existing 8 Supabase tables — clean start, forward-compatible
- [x] Module 1 schema deployed to Supabase (6 tables, RLS enabled, triggers, seed data)
- [x] Repository initialized with project structure

## What's next

- [ ] Build Profile Engine Python script (onboarding questionnaire flow)
- [ ] Claude API integration for CV parsing + skill extraction
- [ ] CLI tool: `datapulse status` command
- [ ] Seed Romi's profile as user #1 (dogfooding)

## Open decisions

- [ ] How to handle skill aliases (e.g., "Postgres" vs "PostgreSQL") — normalization strategy
- [ ] CV upload: PDF parsing library choice (pdfplumber vs PyMuPDF)
=======
- [x] Skills taxonomy: hierarchical `skills` table with `parent_skill_id`, ~50 seed skills
- [x] `user_profiles` fields defined (core, current state, location, learning, career_narrative)
- [x] `user_target_roles` as separate table (supports multiple target roles per user)
- [x] Overlap analysis with existing 8 Supabase tables — clean start, forward-compatible
- [x] CTO system prompt configured with full product context
- [x] Architecture principles defined (9 principles including automation-first, curriculum-aware)

## What's next

- [ ] CTO designs full Module 1 schema (skills, user_profiles, user_skills, work_experience, user_target_roles)
- [ ] Schema review
- [ ] Create GitHub repo `datapulse` with project structure
- [ ] Cursor prompt for SQL migration → run in Supabase
- [ ] Seed skills table with ~50 initial skills
- [ ] Start Profile Engine Python script (questionnaire flow)

## Open decisions

- [ ] Repo name: `datapulse` vs `data-pulse` — decide when creating repo
- [ ] `work_experience` fields — CTO to propose, Romi to review
- [ ] How to handle skill aliases (e.g., "Postgres" vs "PostgreSQL") — normalization strategy
>>>>>>> a215d9e97337a418d223751dae073fdfd6ae12b2

## Key numbers

| Metric | Value |
|--------|-------|
<<<<<<< HEAD
| Build hours spent | ~2 |
| Module 1 estimate | ~20h |
| Tables deployed | 6 (skills, user_profiles, user_target_roles, user_skills, work_experience, work_experience_skills) |
| Skills seeded | 51 (40 top-level + 11 children) |
| RLS policies | 9 |
=======
| Build hours spent | 0 |
| Module 1 estimate | ~20h |
| Total project estimate | ~145h (build) + ~70h (study) |
| Weekly budget | 3–4h |
| Target completion | ~12 months |
>>>>>>> a215d9e97337a418d223751dae073fdfd6ae12b2

## Module progress

| Module | Status | Hours spent |
|--------|--------|-------------|
<<<<<<< HEAD
| 1 — Profile Engine | 🟡 In progress (schema done) | ~2 |
=======
| 1 — Profile Engine | 🟡 In progress (design) | 0 |
>>>>>>> a215d9e97337a418d223751dae073fdfd6ae12b2
| 2 — Market Intelligence Agent | ⬜ Not started | 0 |
| 3 — Skill Gap Analyzer + Reports | ⬜ Not started | 0 |
| 4 — Learning Path Updater + Testing | ⬜ Not started | 0 |
| 5 — Multi-User App (capstone) | ⬜ Not started | 0 |
