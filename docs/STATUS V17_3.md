# DataPulse — Current Status

**Last updated:** 2026-03-20

## Current module: 1 — Profile Engine
## Current phase: Profile seeded, onboarding script complete
## Blocked on: Nothing

---

## What's done

- [x] Product vision defined (5 modules, build order, weekly automated cycle)
- [x] Tech stack decided (Supabase, dbt, Python, Claude API, GitHub Actions, Cursor)
- [x] Repo strategy: new repo `DataPulse`, shared Supabase instance
- [x] Skills taxonomy: hierarchical `skills` table with `parent_skill_id`, ~51 seed skills
- [x] Module 1 schema deployed (migration 001): skills, user_profiles, user_skills, work_experience, work_experience_skills, user_target_roles
- [x] Migration 002 deployed: user_certifications, certification_skills, JSONB columns on user_profiles
- [x] Repo structure: src/datapulse/, migrations/, docs/, .github/workflows/
- [x] Infrastructure: config.py (env loading), db.py (Supabase client), skills_mapper.py (canonical skill lookup with aliases)
- [x] Onboarding questionnaire CLI script (5 sections: identity, work experience, skills, career goals, career story)
- [x] Supabase Auth user created for Romi (real user_id replacing dev placeholder)
- [x] Romi's profile seeded via SQL: 14 skills rated, 3 work experiences, 2 target roles, career narrative
- [x] Column name mismatches fixed (role_title, company_name, confidence as text)

## What's next

- [ ] Phase 4: Claude API integration — CV/LinkedIn parsing into structured profile data
- [ ] Update onboarding script to support LinkedIn text paste → Claude API extraction
- [ ] Seed skills table with any missing skills discovered during onboarding
- [ ] Start Module 2: Market Intelligence Agent (RSS feed collector)

## Key decisions made during Phase 3

- Onboarding simplified from 9 sections (~15 min) to 5 sections (~5 min) — only data that feeds Module 3 skill gap analysis
- Profile seeded via direct SQL instead of questionnaire — faster for user #1, better UX will come in Module 5
- user_languages and platform_access stored as JSONB on user_profiles (not separate tables)
- user_certifications kept as separate table (needed for skill evidence joins in Module 3)
- Real Supabase Auth user created instead of fake DEV_USER_ID — cleaner FK integrity

## Schema note

Actual column names in production (differs from some documentation):
- `user_profiles.role_title` (not current_role — PostgreSQL reserved word)
- `work_experience.role_title` (not job_title)
- `work_experience.company_name` (not company)
- `user_skills.confidence` is text: 'low' / 'medium' / 'high' (not numeric)
- `work_experience` has no `experience_type` column

## Key numbers

| Metric | Value |
|--------|-------|
| Build hours spent | ~6 |
| Module 1 estimate | ~20h |
| Total project estimate | ~145h (build) + ~70h (study) |
| Weekly budget | 3–4h |
| Target completion | ~12 months |

## Module progress

| Module | Status | Hours spent |
|--------|--------|-------------|
| 1 — Profile Engine | 🟡 In progress (profile seeded, script done) | ~6 |
| 2 — Market Intelligence Agent | ⬜ Not started | 0 |
| 3 — Skill Gap Analyzer + Reports | ⬜ Not started | 0 |
| 4 — Learning Path Updater + Testing | ⬜ Not started | 0 |
| 5 — Multi-User App (capstone) | ⬜ Not started | 0 |