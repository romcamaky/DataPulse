# DataPulse

Personal AI career intelligence platform for data analysts and engineers.

DataPulse profiles your skills, monitors the global data/AI ecosystem weekly, compares market demand against your profile, identifies skill gaps, and generates personalized learning recommendations — automatically.

🚀 **Live app:** https://datapulse-jzzz4zerfhvdkhxmbyopzd.streamlit.app

## Status

🟢 **Module 2 — Market Intelligence** is complete (RSS ingestion + Claude signal extraction + biweekly GitHub Actions).

See [STATUS.md](docs/STATUS.md) for current state.

## How it works

```
Every other Sunday (UTC), automatically:

RSS feeds (31 sources) → Claude API signal extraction → dbt transformation (later)
→ skill gap analysis → personalized recommendations → report

Your effort: read the report, approve or reject suggestions. ~5 minutes per cycle.
```

## Tech stack

Supabase (PostgreSQL + Auth + RLS) · dbt Core · Python · Claude API · GitHub Actions · Cursor

## Modules

| # | Module | Status |
|---|--------|--------|
| 1 | Profile Engine | ✅ Complete |
| 2 | Market Intelligence Agent | ✅ Complete |
| 3 | Skill Gap Analyzer + Reports | ✅ Complete |
| 4 | Learning Path Updater + Testing (Learning Lab MVP) | ✅ Complete |
| 5 | Multi-User App (capstone) | 🟡 In progress (web app deployed) |

## Screenshot

_Add app screenshot after deploy._

## Documentation

- [Product Brief](docs/PRODUCT_BRIEF.md) — what this is and why
- [Decision Log](docs/DECISIONS.md) — every architectural decision with reasoning
- [Current Status](docs/STATUS.md) — where the project is right now

## Author

Built by [Romi](https://github.com/romcamaky) as part of the [From Analyst to AI-Native Engineer](https://github.com/romcamaky/AI-Native-Data-Engineer-Journey) journey.

## License

MIT
