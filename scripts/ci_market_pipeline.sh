#!/usr/bin/env bash
# Run once per retry attempt in GitHub Actions (see market_intelligence.yml).
set -euo pipefail

echo "=== DataPulse market pipeline attempt at $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="

# Fail fast with retries when the runner cannot reach Supabase (transient DNS on GHA).
# GitHub-hosted Ubuntu runners occasionally hit short-lived DNS resolver hiccups
# ("Name or service not known"); a longer, backed-off budget here rides those out
# without burning a full outer retry (nick-fields/retry) cycle for a 10-30s blip.
python - <<'PY'
import socket
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

max_attempts = 8
last_exc: Exception | None = None
for attempt in range(1, max_attempts + 1):
    try:
        # Resolve DNS explicitly first so resolver hiccups are logged clearly,
        # separate from auth/HTTP errors raised by the Supabase client below.
        ip = socket.gethostbyname(host)
        print(f"Preflight attempt {attempt}/{max_attempts}: {host} resolved to {ip}")

        client = create_client(url, key)
        client.table("skills").select("id").limit(1).execute()
        print("Preflight: Supabase OK")
        sys.exit(0)
    except Exception as exc:  # noqa: BLE001
        last_exc = exc
        print(f"Preflight attempt {attempt}/{max_attempts} failed: {exc}", file=sys.stderr)
        if attempt < max_attempts:
            sleep_sec = min(10 * attempt, 60)
            print(f"Retrying preflight in {sleep_sec}s …", file=sys.stderr)
            time.sleep(sleep_sec)

print(f"ERROR: Supabase unreachable after {max_attempts} attempts: {last_exc}", file=sys.stderr)
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
