# DataPulse

Personal AI career intelligence platform for data analysts and engineers.

DataPulse profiles your skills, monitors the global data/AI ecosystem weekly, compares market demand against your profile, identifies skill gaps, and generates personalized learning recommendations — automatically.

## Status

🟡 **Module 1 — Profile Engine** (schema design phase)

See [STATUS.md](docs/STATUS.md) for current state.

## How it works

```
Every Sunday, automatically:

RSS feeds (15-20 sources) → Claude API trend extraction → dbt transformation
→ skill gap analysis → personalized recommendations → weekly report

Your effort: read the report, approve or reject suggestions. ~5 minutes/week.
```

## Tech stack

Supabase (PostgreSQL + Auth + RLS) · dbt Core · Python · Claude API · GitHub Actions · Cursor

## Modules

| # | Module | Status |
|---|--------|--------|
| 1 | Profile Engine | 🟡 In progress |
| 2 | Market Intelligence Agent | ⬜ Not started |
| 3 | Skill Gap Analyzer + Reports | ⬜ Not started |
| 4 | Learning Path Updater + Testing | ⬜ Not started |
| 5 | Multi-User App (capstone) | ⬜ Not started |

## Documentation

- [Product Brief](docs/PRODUCT_BRIEF.md) — what this is and why
- [Decision Log](docs/DECISIONS.md) — every architectural decision with reasoning
- [Current Status](docs/STATUS.md) — where the project is right now

## Author

Built by [Romi](https://github.com/romcamaky) as part of the [From Analyst to AI-Native Engineer](https://github.com/romcamaky/AI-Native-Data-Engineer-Journey) journey.

## License

MIT
