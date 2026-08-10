#!/usr/bin/env bash
set -euo pipefail

repo_name="${1:-phoenixnap-ocp422-evpn}"
visibility="${2:-private}"

case "$visibility" in
  private|public|internal) ;;
  *) echo "visibility must be private, public, or internal" >&2; exit 2 ;;
esac

command -v gh >/dev/null || { echo "GitHub CLI (gh) is required." >&2; exit 1; }
gh auth status

if git remote get-url origin >/dev/null 2>&1; then
  echo "origin already exists: $(git remote get-url origin)"
  git push -u origin HEAD
else
  gh repo create "$repo_name" "--${visibility}" --source=. --remote=origin --push
fi
