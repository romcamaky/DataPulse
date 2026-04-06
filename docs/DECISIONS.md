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

**Why:** Limited time budget means every minute of manual work is expensive. Copy-paste between systems is a design failure.

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

**Why:** All users consume the same 31 RSS feeds. Storing per-user duplicates wastes space and complicates deduplication. The personalization happens in Module 3 where dbt models JOIN market_signals (global) against user_skills (per-user) to produce individualized gap analysis. RLS allows all authenticated users to read; only the service role pipeline can write.

**Also decided:** Added `confidence` column (1-5) on market_signals so Claude rates its extraction certainty. Costs zero extra tokens, enables Module 3 to filter low-confidence noise (WHERE confidence >= 3).

**Decided by:** Romi + CTO

---

## 2026-03-20 | Access control — invite-only registration

**Decision:** DataPulse will use invite-only registration. Only whitelisted email addresses can sign up. No open self-registration.

**Why:** The public GitHub repo exposes the codebase but not the infrastructure. Once Module 5 adds a web frontend with Supabase Auth, open registration would let strangers trigger Claude API calls at the owner's expense. Invite-only (whitelist of allowed emails checked at signup) eliminates this risk. Current users: Romi + Petr (added directly via Supabase Auth dashboard).

**Implementation:** `allowed_emails` whitelist checked at login. Registration tab removed from the app entirely.

**Decided by:** Romi + CTO

---

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

---

## 2026-03-21 | RSS feed selection — 31 feeds across 7 categories

**Decision:** Curate 31 RSS feeds across 7 categories (vendors, AI research, community, industry, practitioner, EU regulation, CZ/CEE). No job board scraping.

**Why:** RSS is stable, legal, and sufficient for trend signals. Job boards have legal risk and fragile CSS selectors. Seven categories ensure coverage across tools, research, adoption, regulation, and local market. Czech-language feeds (Lupa, Root, CzechCrunch) are included for Prague/CEE market relevance.

**Decided by:** Romi + CTO

---

## 2026-03-22 | Two-tier Claude API — Haiku for extraction, Sonnet for personalization

**Decision:** Use a two-tier Claude API strategy: Haiku for high-volume structured extraction (RSS → `market_signals`). Reserve Sonnet for personalized generation (recommendations, study docs, theory).

**Why:** Extraction is classification — fast, cheap, and does not need deep reasoning. Personalization needs quality. A full pipeline run costs roughly $0.30 with Haiku for extraction. Using Sonnet for extraction would cost an order of magnitude more with no meaningful quality gain for that task.

**Decided by:** Romi + CTO

---

## 2026-03-22 | Recommender RLS — INSERT restricted to service role

**Decision:** `authenticated` role has INSERT denied (`WITH CHECK (false)`) on `recommendations`. Only the service role (used by the Python pipeline) can write recommendations.

**Why:** Same pattern as `market_signals`. The recommender runs as a backend pipeline, not as an authenticated user. Allowing authenticated INSERT would open a privilege escalation vector in a multi-user app. Service role bypasses RLS by design — this is the correct Supabase pattern for server-side writes.

**Decided by:** Cursor (proposed), CTO (approved)

---

## 2026-03-22 | Recommender prompt — framework exclusion list

**Decision:** Recommender prompt must explicitly instruct Claude not to recommend LangChain, CrewAI, FastAPI, or Airflow as learning resources or tools.

**Why:** These are excluded from the DataPulse tech stack by design (see 2026-03-17 decision). A recommendation to "learn LangChain" contradicts the architectural decisions already logged and would confuse the user. The model has no awareness of project-level constraints unless explicitly told.

**Implementation:** Constraints block in the recommender system prompt listing excluded tools and preferred simpler alternatives.

**Decided by:** CTO observed in Module 3 output, Romi approved

---

## 2026-03-22 | Module 4 scope — defer pytest suite and approve/reject CLI

**Decision:** Ship Module 4 without the pytest suite and approve/reject CLI. Both are deferred until the user profile is updated with real, complete data.

**Why:** Tests written against sparse profile data lock in incomplete behavior. The approve/reject CLI only matters once recommendations are being acted on regularly. Neither omission blocks the pipeline or the portfolio story.

**Deferred to:** After profile data is complete.

**Decided by:** Romi

---

## 2026-03-22 | system-overview.md as living architecture document

**Decision:** `docs/architecture/system-overview.md` is the single source of truth for system architecture. It must be updated whenever a new module ships or a significant architectural change is made.

**Why:** Recruiters and interviewers read docs, not code. A maintained architecture document with a rendered Mermaid diagram is a stronger portfolio signal than comments scattered across files.

**Decided by:** Romi + CTO

---

## 2026-03-23 | Learning Lab schema alignment

**Decision:** Use actual migration schema for assessment_results and curriculum_progress instead of prompt spec columns.

**Why:** assessment_results requires session_id (FK), not topic_id directly. curriculum_progress uses best_score + attempts, not score_percentage. Fallback logic was removed in favor of single correct code path.

**Decided by:** CTO (schema mismatch caught before runtime)

---

## 2026-03-23 | topic_skill_mapping seed

**Decision:** Map Topics 1–5 to sql, query_optimization, ctes, window_functions skills only.

**Why:** These are the skills directly practiced in SQL topics. Broader skill inference deferred to Module 3 gap analysis.

**Decided by:** CTO

---

## 2026-03-23 | Streamlit frontend over React

**Decision:** Use Streamlit for Module 5 frontend. React deferred indefinitely.

**Why:** Python-only — no JS knowledge required. Free hosting on Streamlit Community Cloud. Cursor generates UI from prompts. For a portfolio capstone, a shipped working product beats a half-built React app. Streamlit's multi-page architecture with native session state sharing is sufficient for the current scope.

**Decided by:** Romi + CTO

---

## 2026-03-23 | Multi-page auth — get_authenticated_client() pattern

**Decision:** Every Streamlit page rebuilds the Supabase client from session state tokens via a shared `get_authenticated_client()` helper, called at the top of each page's `main()`.

**Why:** Streamlit re-runs the entire script on every interaction, and navigating between pages in a multi-page app loses the client object from session state. Rebuilding from stored tokens on every page load is the correct pattern — stateless by design, no client object serialization needed.

**Decided by:** CTO

---

## 2026-03-23 | Persistent login — streamlit-cookies-controller

**Decision:** Use `streamlit-cookies-controller` to persist the Supabase session token across browser restarts. Added to `pyproject.toml` dependencies.

**Why:** Without cookie persistence, users must log in every time they open the app. Storing the JWT in a browser cookie and restoring it on app load gives standard web app UX. Alternative (localStorage) is not accessible from Streamlit's Python runtime.

**Decided by:** CTO recommended, Romi approved

---

## 2026-03-23 | dbt profiles.yml — committed to repo

**Decision:** `dbt/profiles.yml` is force-added to git (overriding `.gitignore`). The GitHub Actions dbt step uses `--profiles-dir .` flag.

**Why:** dbt by default reads profiles from `~/.dbt/profiles.yml` (user home). In GitHub Actions there is no home directory with a pre-seeded profiles file. Committing `profiles.yml` to the repo (with env vars, not hardcoded secrets) is the standard CI/CD pattern. Secrets are injected via GitHub Actions environment variables.

**Decided by:** CTO

---

## 2026-03-23 | Supabase connection — session pooler over direct connection

**Decision:** Use session pooler host `aws-1-eu-central-1.pooler.supabase.com:5432` for all dbt and Python connections. Direct connection host (`db.aqdonqswhgabydwycxjo.supabase.co`) is not used.

**Why:** The direct connection host resolves to an IPv6-only address on Romi's network and in GitHub Actions. The session pooler resolves to IPv4 consistently. Port 5432 (not 6543) is used because dbt requires a persistent connection, not transaction-mode pooling.

**Decided by:** CTO diagnosed, Romi confirmed fix

---

## 2026-03-24 | Biweekly pipeline instead of weekly

**Decision:** GitHub Actions cron runs the pipeline every two weeks, not weekly.

**Why:** Enough signal accumulates for one to two active users at half the API cost. Weekly would be premature optimization before multiple active users exist.

**Decided by:** Romi + CTO

---

## 2026-03-25 | Global market signals — no user_id on feed_items or market_signals

**Decision:** `feed_items` and `market_signals` are global tables, not per-user.

**Why:** The same article is relevant to all users. Personalization happens downstream in dbt models that join global signals against per-user `user_skills`. Duplicating signals per user would waste storage and complicate the pipeline.

**Decided by:** Romi + CTO

---

## 2026-03-26 | Skill aliases normalization

**Decision:** Create a `skill_aliases` mapping (roughly 290 entries) to resolve variant names ("Postgres" → "PostgreSQL", "AI agents" → "AI Agents") to canonical skill IDs.

**Why:** A large share of market signals had NULL `skill_id` due to name mismatches. Without normalization, skill gap analysis was blind. The alias table plus a backfill script fixed historical data and prevents future mismatches.

**Decided by:** Romi + CTO

---

## 2026-03-27 | mart_trend_summary — normalize trending_score to 0–10

**Decision:** `trending_score` in `mart_trend_summary` is normalized to 0–10 via window function (`raw_trending_score / max(raw_trending_score) over () * 10`). `raw_trending_score` is retained as a separate column for debugging.

**Why:** The raw formula (`signal_count × avg_strength × avg_confidence / 10`) produces unbounded values (observed max: 108). A normalized 0–10 scale is user-readable, consistent with gap scores, and correct for display in reports and the app. Normalization is relative — the top skill always scores 10.

**Decided by:** CTO

---

## 2026-03-28 | Custom demand and gap scoring formulas

**Decision:** Demand score = `round((avg_strength × 0.6 + avg_confidence × 0.4) × ln(signal_count + 1), 2)`. Gap score = `round(demand_score × (5 − user_level) / 5.0, 2)`.

**Why:** Logarithmic signal count prevents a single noisy feed from dominating. Weighting strength over confidence reflects that a strong signal from one source matters more than many weak signals. Gap score scales inversely with user level — a skill you already know well has a low gap regardless of demand.

**Decided by:** Romi + CTO

---

## 2026-03-29 | Custom unique_combination_of_columns macro instead of dbt_utils

**Decision:** Implement a roughly 10-line custom macro rather than importing the `dbt_utils` package.

**Why:** Avoids an external package dependency for a single function. No version-pinning overhead. Fully owned and explainable in code review and interviews.

**Decided by:** Romi + CTO

---

## 2026-03-30 | One Claude Sonnet call per user for recommendations

**Decision:** Batch all skills for one user into a single Sonnet prompt, not one call per skill.

**Why:** Cost control — Sonnet is expensive. Batching produces comparable quality at a fraction of the cost. One call with `max_tokens: 4096` covers the full skill profile.

**Decided by:** Romi + CTO

---

## 2026-03-31 | Session pooler instead of direct Supabase connection

**Decision:** Use `aws-1-eu-central-1.pooler.supabase.com:5432` for dbt and script connections to PostgreSQL.

**Why:** The direct connection host resolves to IPv6-only on the development network. The session pooler works consistently. Pragmatic fix over network reconfiguration.

**Decided by:** CTO diagnosed, Romi confirmed

---

## 2026-04-01 | Streamlit over React

**Decision:** Build the frontend in Streamlit, not React.

**Why:** Python-only — no JavaScript knowledge required. Free hosting on Streamlit Community Cloud. Cursor generates UI from prompts. Shipping a working product beats a half-built React app. Multi-page layout with native auth state sharing covers all requirements.

**Decided by:** Romi + CTO

---

## 2026-04-03 | Hybrid tutor — DB questions plus Claude grading

**Decision:** Pre-seed questions in `questions_bank` (zero API cost to display). Claude Haiku or Sonnet activates only for grading answers.

**Why:** Assessment of five questions costs roughly $0.01–0.025. Controllable cost with personalized feedback. Pure LLM-generated questions would be expensive and unpredictable.

**Decided by:** Romi + CTO

---

## 2026-04-05 | Learning Lab integrated into DataPulse, not a separate app

**Decision:** Learning Lab is a page within DataPulse, not a standalone application.

**Why:** Shared auth state, one deployment, direct connection to skill profile. When a user passes an assessment, `topic_skill_mapping` auto-updates `user_skills`. Studying and career intelligence stay one closed loop.

**Decided by:** Romi + CTO

---

## 2026-04-07 | Curriculum expansion to 28 topics

**Decision:** Expand from 20 data-engineering-only topics to 28: original 20 plus AI Literacy (21–24) plus Business Analysis (25–28).

**Why:** Target roles (for example AI Solutions Analyst, Analytics Engineer) require AI literacy and business analysis skills beyond pure data engineering. The curriculum must match the career intelligence the platform provides.

**Decided by:** Romi + CTO

---

## 2026-04-09 | Skills taxonomy restructured to six categories

**Decision:** Restructure skill categories to: `language`, `framework`, `platform_tool`, `engineering`, `ai_ml`, `soft_skill`.

**Why:** Original categories were too coarse. Separating AI/ML from general engineering and adding `soft_skill` allows more precise gap analysis and better-targeted recommendations.

**Decided by:** Romi + CTO

---

## 2026-04-11 | Study documentation system — auto-generated per-user notes

**Decision:** After Learning Lab sessions, Claude Sonnet generates personalized study notes. Store them in `study_documentation` with a `(user_id, topic_id)` unique constraint. Merge with existing notes on repeat sessions.

**Why:** Turns every practice and assessment session into a persistent study artifact. Users build a personal knowledge base automatically. Merge-on-repeat ensures notes accumulate rather than overwrite.

**Decided by:** Romi + CTO

---

## 2026-04-13 | Learn Mode with pre-seeded theory content

**Decision:** Create `theory_content` (global, SELECT-only RLS) with structured markdown per topic. Seed via `seed_theory.py` using Claude Sonnet. The Learn page renders theory and allows Claude Q&A that feeds into `study_documentation`.

**Why:** Learning Lab tests knowledge but does not teach it. Learn Mode fills the gap — users can study theory, ask follow-up questions, and interactions accumulate into study notes.

**Decided by:** Romi + CTO

---

## 2026-04-15 | Downloads page — Markdown and PDF export

**Decision:** Add a Downloads page offering per-topic and combined study guide export as Markdown and PDF (via `fpdf2`).

**Why:** Users need offline access to study materials. Markdown for portability, PDF for printing and sharing. The combined guide aggregates all topics into one document.

**Decided by:** Romi + CTO

---

## 2026-04-17 | Practice mode — study docs every third answer

**Decision:** In practice mode, study documentation generation triggers every third answered question, not after every answer.

**Why:** Generating study docs after every practice answer is expensive (Sonnet each time) and produces fragmented notes. Batching every three answers balances cost with useful content accumulation.

**Decided by:** Romi + CTO
