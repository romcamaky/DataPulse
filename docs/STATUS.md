# DataPulse — Current Status

**Last updated:** 2026-03-17

## Current module: 1 — Profile Engine
## Current phase: Schema design
## Blocked on: Nothing

---

## What's done

- [x] Product vision defined (5 modules, build order, weekly automated cycle)
- [x] Tech stack decided (Supabase, dbt, Python, Claude API, GitHub Actions, Cursor)
- [x] Repo strategy: new repo `datapulse`, shared Supabase instance
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

## Key numbers

| Metric | Value |
|--------|-------|
| Build hours spent | 0 |
| Module 1 estimate | ~20h |
| Total project estimate | ~145h (build) + ~70h (study) |
| Weekly budget | 3–4h |
| Target completion | ~12 months |

## Module progress

| Module | Status | Hours spent |
|--------|--------|-------------|
| 1 — Profile Engine | 🟡 In progress (design) | 0 |
| 2 — Market Intelligence Agent | ⬜ Not started | 0 |
| 3 — Skill Gap Analyzer + Reports | ⬜ Not started | 0 |
| 4 — Learning Path Updater + Testing | ⬜ Not started | 0 |
| 5 — Multi-User App (capstone) | ⬜ Not started | 0 |
