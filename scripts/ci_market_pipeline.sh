#!/usr/bin/env bash
# Run once per retry attempt in GitHub Actions (see market_intelligence.yml).
set -euo pipefail

echo "=== DataPulse market pipeline attempt at $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="

# Best-effort RSS collection (same as workflow continue-on-error).
if ! python -m datapulse.collector; then
  echo "WARNING: collector exited non-zero; continuing with extractor."
fi

python -m datapulse.extractor

pip install -q dbt-postgres
(
  cd dbt
  dbt run --profiles-dir .
  dbt test --profiles-dir .
)

python -m datapulse.report

echo "=== Pipeline attempt succeeded ==="
