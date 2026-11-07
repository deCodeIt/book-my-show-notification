#!/usr/bin/env bash
# Brings the notifier container up. Safe to run repeatedly.
# Invoked by the LaunchAgent at login, and usable by hand.
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"

docker_ready() {
  docker info >/dev/null 2>&1
}

if ! docker_ready; then
  # Docker Desktop is not set to start at login on this machine, so launch it
  # ourselves and give the VM time to boot.
  open -a Docker >/dev/null 2>&1 || true
  for _ in $(seq 1 60); do
    docker_ready && break
    sleep 3
  done
fi

if ! docker_ready; then
  echo "Docker daemon did not become ready after 3 minutes" >&2
  exit 1
fi

cd "$PROJECT_DIR"
exec docker compose up -d --remove-orphans
