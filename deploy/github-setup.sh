#!/usr/bin/env bash
# Idempotent GitHub repo setup for the deploy pipeline (vars, secrets, Pages) + push main.
# Run from the repo root:  bash deploy/github-setup.sh
# Uses $GH_TOKEN if set, else the GH_TOKEN line of ./.env (never printed).
set -euo pipefail

R=${REPO:-SuperThinking/tilefolio}
DEPLOY_HOST=${DEPLOY_HOST:-139.84.221.234}
BACKEND_HOST=${BACKEND_HOST:-139-84-221-234.sslip.io}
CI_KEY=${CI_KEY:-$HOME/.ssh/tilefolio_ci}

if [[ -z "${GH_TOKEN:-}" && -f .env ]]; then
  GH_TOKEN=$(sed -n 's/^GH_TOKEN:[[:space:]]*//p' .env | head -1)
fi
export GH_TOKEN
[[ -n "${GH_TOKEN:-}" ]] || { echo "GH_TOKEN not set (and not found in .env)" >&2; exit 1; }
[[ -f "$CI_KEY" ]] || { echo "missing deploy key $CI_KEY" >&2; exit 1; }

echo "== variables"
gh variable set BACKEND_HOST -R "$R" --body "$BACKEND_HOST"
gh variable set DEPLOY_HOST -R "$R" --body "$DEPLOY_HOST"

echo "== secrets"
gh secret set DEPLOY_SSH_KEY -R "$R" < "$CI_KEY"
known=$(ssh-keyscan -t ed25519 "$DEPLOY_HOST" 2>/dev/null)
[[ "$known" == *ssh-ed25519* ]] || { echo "ssh-keyscan failed for $DEPLOY_HOST" >&2; exit 1; }
printf '%s\n' "$known" | gh secret set DEPLOY_KNOWN_HOSTS -R "$R"

echo "== pages (source = GitHub Actions)"
gh api "repos/$R/pages" --jq .html_url 2>/dev/null || gh api -X POST "repos/$R/pages" -f build_type=workflow --jq .html_url

echo "== push"
git -c credential.helper= -c 'credential.helper=!gh auth git-credential' push -u origin main

echo "== done. Watch: gh run watch -R $R"
