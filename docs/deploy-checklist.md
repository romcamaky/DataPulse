# Deploy checklist — Streamlit Community Cloud

1. Push repo to GitHub (must be public or connected private repo)
2. Go to share.streamlit.io → New app
3. Select repo, branch: main, main file: app.py
4. Under Advanced → Secrets, paste:

SUPABASE_URL = "https://your-project.supabase.co"
SUPABASE_ANON_KEY = "your-anon-key"
ANTHROPIC_API_KEY = "your-anthropic-key"

5. Deploy
6. After deploy: update Supabase Auth → URL Configuration
   - Site URL: https://your-app.streamlit.app
   - Redirect URLs: https://your-app.streamlit.app/*

---

## GitHub Actions — pipeline failure email

Repo → **Settings → Secrets and variables → Actions** → add:

| Secret | Example | Purpose |
|--------|---------|---------|
| `PIPELINE_ALERT_EMAIL` | your@email.com | Recipient when all 5 attempts fail |
| `SMTP_HOST` | `smtp.gmail.com` | Outbound mail server |
| `SMTP_PORT` | `465` | TLS port (587 for STARTTLS — see action docs) |
| `SMTP_USERNAME` | your@gmail.com | SMTP login |
| `SMTP_PASSWORD` | app-specific password | SMTP password (not your Google account password) |

Existing pipeline secrets (`SUPABASE_*`, `ANTHROPIC_API_KEY`, DB vars) stay unchanged.

The workflow retries every **5 minutes**, up to **5 times**, then sends one alert email with a link to the failed run.
