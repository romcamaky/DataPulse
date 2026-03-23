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
