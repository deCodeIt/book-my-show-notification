#!/usr/bin/env bash
# Brings the container up. Safe to run repeatedly.
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"

# launchd starts us before Docker Desktop is necessarily ready.
if ! docker info >/dev/null 2>&1; then
  open -a Docker >/dev/null 2>&1 || true
  for _ in $(seq 1 40); do
    docker info >/dev/null 2>&1 && break
    sleep 3
  done
fi

cd "$PROJECT_DIR"
exec docker compose up -d
