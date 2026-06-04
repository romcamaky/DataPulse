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

# dbt-postgres 1.10 alone can resolve to dbt-core 2.0 (Fusion) since 2026-06-01; pin core <2.
pip install -q --force-reinstall "dbt-core>=1.10,<2" "dbt-postgres==1.10.0"
DBT_EXE="$(dirname "$(command -v python)")/dbt"
if [[ ! -x "$DBT_EXE" ]]; then
  echo "ERROR: pip dbt not found at ${DBT_EXE}" >&2
  exit 1
fi
DBT_CORE_VER="$(python -c 'import importlib.metadata as m; print(m.version("dbt-core"))')"
echo "dbt-core ${DBT_CORE_VER} (${DBT_EXE})"
case "$DBT_CORE_VER" in
  1.*) ;;
  *)
    echo "ERROR: expected dbt-core 1.x (postgres adapter), got ${DBT_CORE_VER}" >&2
    "$DBT_EXE" --version >&2 || true
    exit 1
    ;;
esac
(
  cd dbt
  "$DBT_EXE" run --profiles-dir .
  "$DBT_EXE" test --profiles-dir .
)

python -m datapulse.report

echo "=== Pipeline attempt succeeded ==="
