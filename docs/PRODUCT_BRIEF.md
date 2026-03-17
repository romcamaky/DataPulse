# DataPulse — Product Brief

## What is DataPulse

DataPulse is a personal AI career intelligence platform for data analysts and engineers. It builds a complete profile of the user's skills, then continuously monitors the global data/AI ecosystem, compares market demand against the user's profile, identifies skill gaps, and generates personalized learning recommendations — all automatically.

The user's only weekly interaction: read a report, approve or reject suggested changes to their learning plan. Everything else runs on its own.

This is also a public portfolio project. Every component demonstrates real data engineering, analytics engineering, and AI integration skills. The code lives on GitHub, the architecture is documented, and the author can walk through every decision in an interview.

---

## Architecture Overview

```
┌─────────────────────────────────────┐
│         PRESENTATION LAYER          │
│  Web app (Lovable → Streamlit/React)│
│  Weekly reports (markdown → GitHub) │
│  DataPulse CLI tool                 │
└──────────────────┬──────────────────┘
                   │
┌──────────────────┴──────────────────┐
│        INTELLIGENCE LAYER           │
│  Claude API:                        │
│  - Skill extraction from CV/input   │
│  - Trend analysis from articles     │
│  - Gap detection & recommendations  │
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
| Intelligence | Claude API (Anthropic) | Content analysis, skill extraction, recommendations |
| Automation | GitHub Actions | Weekly cron, CI/CD, zero infrastructure cost |
| Frontend (now) | Lovable | Fast iteration, already deployed |
| Frontend (later) | Streamlit or React via Cursor | Capstone module |
| Dev tool | Cursor AI | Primary code generation tool |
| Version control | GitHub | Public repo — this is a portfolio project |

**Explicitly NOT using:** LangChain, CrewAI, FastAPI, Airflow, job board scraping. Simpler tools solve every problem here.

---

## 5 Modules — Build Order

### Module 1: Profile Engine (Month 1–2, ~20h)

Structured onboarding — questionnaire + CV upload. Claude API extracts structured skill data. Stores in Supabase (user_profiles, user_skills, work_experience). Each skill has level, confidence, evidence_type, visibility. Supports confidential work projects.

Curriculum alignment: Python fundamentals (Topics 9–10).

### Module 2: Market Intelligence Agent (Month 3–4, ~20h)

Python script fetches 15–20 curated RSS feeds weekly. Claude API batch-analyzes articles → extracts technologies, trends, skill demands → stores in market_signals. Runs automatically every Sunday via GitHub Actions cron.

Curriculum alignment: APIs + databases (Topics 11–12).

### Module 3: Skill Gap Analyzer + Reports (Month 5–6, ~20h)

dbt models join market_signals with user_skills to produce a skill gap mart. Python + Pandas aggregates trends. Claude API generates personalized recommendations. Markdown report auto-commits to GitHub. User gets notified.

Curriculum alignment: Pandas (Topic 13) + dbt in depth (Topics 15–17).

### Module 4: Learning Path Updater + Testing (Month 7–8, ~15h)

Approved recommendations auto-update curriculum priorities. Full pytest suite for entire pipeline. Monitoring, freshness checks, architecture documentation.

Curriculum alignment: Testing (Topic 14) + DE concepts (Topics 18–20).

### Module 5: Multi-User App — Capstone (Month 9–12, ~40h)

Supabase Auth, RLS policies, web frontend with onboarding flow, dashboard, reports. Any user can register and get personalized career intelligence.

Curriculum alignment: Integration of everything.

---

## Weekly Automated Cycle

Every Sunday at 6:00 UTC, zero human input:

1. RSS Collector → fetch feeds → store raw in Supabase
2. Claude API → analyze articles → extract signals
3. dbt build → staging → intermediate → skill gap marts
4. Claude API → gap data → personalized recommendations
5. Report Generator → markdown → auto-commit to GitHub
6. Notification → email/Slack: "Your report is ready"
7. Learning Path Update → pending_recommendations for approval

User's weekly effort: ~5 minutes.

---

## Constraints

- **Time:** ~3–4 hours/week for building
- **Budget:** Supabase free tier, Claude API pay-per-use
- **Public repo:** Code quality, documentation, commit history matter
- **Multi-user from day 1:** Every table has user_id, every query is RLS-scoped
- **No shortcuts I can't explain:** Must understand architecture for interviews
- **Automation over manual:** Every recurring task gets automated

---

## Existing Infrastructure

- Supabase instance: 8 tables, RLS enabled, Frankfurt region
- dbt project: 7 models (6 staging + 1 intermediate), 32 tests passing
- GitHub Actions CI: runs dbt build + test on every PR
- GitHub repo: github.com/romcamaky/AI-Native-Data-Engineer-Journey
- Portfolio site: ai-native-data-engineer-journey.lovable.app

---

## What This Project Proves

| Target Role | What DataPulse demonstrates |
|-------------|----------------------------|
| Junior Data Engineer | Ingestion pipeline, orchestration, dbt, CI/CD, error handling |
| Analytics Engineer | dbt modeling over real data, testing, documentation |
| AI / Data Designer | Claude API in pipeline, prompt engineering in code, system design |
| Data Analyst + AI | Skill gap analysis, trend detection, automated reporting |
