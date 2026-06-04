#!/usr/bin/env bash
# Run once per retry attempt in GitHub Actions (see market_intelligence.yml).
set -euo pipefail

echo "=== DataPulse market pipeline attempt at $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="

# Fail fast with retries when the runner cannot reach Supabase (transient DNS on GHA).
python - <<'PY'
import os
import sys
import time
from urllib.parse import urlparse

from supabase import create_client

url = os.environ.get("SUPABASE_URL", "").strip()
key = os.environ.get("SUPABASE_KEY", "").strip()
if not url or not key:
    print("ERROR: SUPABASE_URL and SUPABASE_KEY must be set.", file=sys.stderr)
    sys.exit(1)

host = urlparse(url).hostname or url
print(f"Preflight: checking Supabase connectivity ({host}) …")

last_exc = None
for attempt in range(1, 6):
    try:
        client = create_client(url, key)
        client.table("skills").select("id").limit(1).execute()
        print("Preflight: Supabase OK")
        sys.exit(0)
    except Exception as exc:  # noqa: BLE001
        last_exc = exc
        print(f"Preflight attempt {attempt}/5 failed: {exc}", file=sys.stderr)
        if attempt < 5:
            time.sleep(10)

print(f"ERROR: Supabase unreachable after 5 attempts: {last_exc}", file=sys.stderr)
sys.exit(1)
PY

# Best-effort RSS collection (same as workflow continue-on-error).
if ! python -m datapulse.collector; then
  echo "WARNING: collector exited non-zero; continuing with extractor."
fi

python -m datapulse.extractor

# Pin 1.x: unversioned install recently pulled dbt-core 2.0 (Fusion), which rejects postgres.
pip install -q "dbt-postgres==1.10.0"
(
  cd dbt
  dbt run --profiles-dir .
  dbt test --profiles-dir .
)

python -m datapulse.report

echo "=== Pipeline attempt succeeded ==="
