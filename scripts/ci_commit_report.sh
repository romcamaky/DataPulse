#!/usr/bin/env bash
# Commit docs/reports and push; safe to re-run when a previous push failed after commit.
set -euo pipefail

BRANCH="${GITHUB_REF_NAME:-main}"

git config user.name "DataPulse Bot"
git config user.email "datapulse-bot@users.noreply.github.com"

git fetch origin "${BRANCH}"

git add docs/reports/

if ! git diff --staged --quiet; then
  git commit -m "chore: weekly career intelligence report $(date -u +%Y-%m-%d) [skip ci]"
fi

if git rev-parse "origin/${BRANCH}" >/dev/null 2>&1; then
  ahead="$(git rev-list --count "origin/${BRANCH}..HEAD" 2>/dev/null || echo 0)"
else
  ahead=1
fi

if [ "${ahead}" = "0" ]; then
  echo "No report changes to commit or push."
  exit 0
fi

git pull --rebase origin "${BRANCH}"
git push origin "HEAD:${BRANCH}"

echo "Report committed and pushed to origin/${BRANCH}."
