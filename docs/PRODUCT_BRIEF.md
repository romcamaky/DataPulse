# DataPulse — Product Brief

## What is DataPulse

DataPulse is a personal AI career intelligence platform for data analysts and engineers. It builds a complete profile of the user's skills, then continuously monitors the global data/AI ecosystem, compares market demand against the user's profile, identifies skill gaps, and generates personalized learning recommendations — all automatically.

The user's main recurring interaction: every two weeks, read a report and approve or reject suggested changes to their learning plan. Everything else runs on its own.

This is also a public portfolio project. Every component demonstrates real data engineering, analytics engineering, and AI integration skills. The code lives on GitHub, the architecture is documented, and the author can walk through every decision in an interview.

---

## Architecture Overview

```
┌─────────────────────────────────────┐
│         PRESENTATION LAYER          │
│  Streamlit multi-page app           │
│  Biweekly reports (markdown → GitHub)│
│  DataPulse CLI tool                 │
└──────────────────┬──────────────────┘
                   │
┌──────────────────┴──────────────────┐
│        INTELLIGENCE LAYER           │
│  Claude Haiku: extraction, grading  │
│  Claude Sonnet: recommendations,   │
│    study docs, theory               │
│  (CV/skill input, articles, gaps)   │
└──────────────────┬──────────────────┘
                   │
┌──────────────────┴──────────────────┐
│        TRANSFORMATION LAYER         │
│  dbt Core (PostgreSQL adapter):     │
│  - staging → intermediate → marts   │
│  - Skill gap marts                  │
│  - Trend aggregation models         │
└──────────────────┬──────────────────┘
                   │
┌──────────────────┴──────────────────┐
│           DATA LAYER                │
│  Supabase (PostgreSQL):             │
│  - user_profiles, user_skills       │
│  - work_experience                  │
│  - market_signals                   │
│  - recommendations                  │
│  + Supabase Auth + RLS (multi-user) │
└─────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Tool | Why |
|-------|------|-----|
| Database & Auth | Supabase (PostgreSQL + Auth + RLS) | Already running, free tier, multi-user ready |
| Transformations | dbt Core + postgres adapter | 3-layer modeling, testable, portfolio-grade |
| Backend/Pipeline | Python | Ingestion scripts, Claude API calls, CLI tool |
| Intelligence | Claude API (Anthropic) | **Haiku** for high-volume extraction and answer grading; **Sonnet** for recommendations, study documentation, and theory — cost-conscious split |
| Automation | GitHub Actions | Biweekly cron (Sunday 06:00 UTC), CI/CD, zero infrastructure cost |
| Frontend | Streamlit | Python-only, free Community Cloud hosting, multi-page with native auth |
| Dev tool | Cursor AI | Primary code generation tool |
| Version control | GitHub | Public repo — this is a portfolio project |

**Explicitly NOT using:** LangChain, CrewAI, FastAPI, Airflow, job board scraping. Simpler tools solve every problem here.

---

## Modules

### Module 1: Profile Engine

Structured onboarding — questionnaire + CV upload. Claude API extracts structured skill data. Stores in Supabase (user_profiles, user_skills, work_experience). Each skill has level, confidence, evidence_type, visibility. Supports confidential work projects.

### Module 2: Market Intelligence Agent

Python script fetches 31 curated RSS feeds across seven categories. Claude Haiku batch-analyzes articles → extracts technologies, trends, skill demands → stores in market_signals. Runs automatically on a biweekly schedule via GitHub Actions cron (Sunday 06:00 UTC).

### Module 3: Skill Gap Analyzer + Reports

dbt models join market_signals with user_skills to produce a skill gap mart. Python aggregates trends. Claude Sonnet generates personalized recommendations. Markdown report auto-commits to GitHub.

### Module 4: Learning Path Updater

Approved recommendations update curriculum priorities. Architecture documentation and automated report flow; deeper test automation where it adds value.

### Module 5: Multi-User App — Capstone

Supabase Auth, RLS policies, Streamlit multi-page frontend with onboarding flow, dashboard, recommendations, and biweekly reports. Learning Lab for practice and assessment with AI grading; Learn Mode for theory content and Q&A; study documentation generated from sessions; Downloads page for Markdown and PDF exports; invite-only access for cost control.

### Post-launch features

- **Study Documentation** — auto-generated personalized notes after Learning Lab sessions, merged over time per topic.
- **Learn Mode** — pre-seeded theory content per topic plus Claude Q&A that feeds study notes.
- **Downloads page** — per-topic and combined study guides as Markdown and PDF.
- **Curriculum expansion** — 28 topics (20 data engineering + 4 AI literacy + 4 business analysis).
- **Skills taxonomy** — six categories for finer gap analysis (`language`, `framework`, `platform_tool`, `engineering`, `ai_ml`, `soft_skill`).
- **Practice mode** — study documentation generation batched every third answered question to balance cost and usefulness.

---

## Biweekly Automated Cycle

Every two weeks, on Sunday at 06:00 UTC, zero human input:

1. RSS Collector → fetch feeds → store raw in Supabase (`feed_items`)
2. Claude Haiku → analyze articles → extract signals → `market_signals`
3. dbt build → staging → intermediate → skill gap marts
4. Claude Sonnet → gap data → personalized recommendations
5. Report Generator → markdown → auto-commit to GitHub
6. Recommendations surface in the app → user approves or rejects

Your effort: read the report, approve or reject suggestions.

---

## Constraints

- **Budget:** Supabase free tier, Claude API pay-per-use
- **Public repo:** Code quality, documentation, commit history matter
- **Multi-user from day 1:** Every table has user_id, every query is RLS-scoped
- **No shortcuts I can't explain:** Must understand architecture for interviews
- **Automation over manual:** Every recurring task gets automated

---

## Existing Infrastructure

- Supabase instance: 19 tables, RLS on all, Frankfurt region
- dbt project: 11 models (6 staging + 3 intermediate + 2 marts), 42+ tests
- GitHub Actions: biweekly market intelligence pipeline; dbt build + test on PRs as configured
- Streamlit Community Cloud: live app deployment
- GitHub repo: [github.com/romcamaky/DataPulse](https://github.com/romcamaky/DataPulse)

---

## What This Project Proves

| Target Role | What DataPulse demonstrates |
|-------------|----------------------------|
| Junior Data Engineer | Ingestion pipeline, orchestration, dbt, CI/CD, error handling |
| Analytics Engineer | dbt modeling over real data, testing, documentation |
| AI / Data Designer | Claude API in pipeline, prompt engineering in code, system design |
| Data Analyst + AI | Skill gap analysis, trend detection, automated reporting |
| AI Solutions Analyst | Two-tier Claude strategy (Haiku vs Sonnet), prompt engineering, AI-augmented product delivery, cost-conscious AI design |
