#!/usr/bin/env bash
# LaunchAgent entry point. Installed to an internal-disk path because macOS
# denies launchd-spawned processes access to external volumes.
#
# Only talks to the Docker daemon, so it never needs the project directory:
# the container (with restart: unless-stopped) already lives inside Docker.
set -uo pipefail

LABEL="bms-notifier"
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"

docker_ready() {
  docker info >/dev/null 2>&1
}

if ! docker_ready; then
  # Docker Desktop is not set to start at login on this machine, so start it
  # and give the VM time to boot (a cold start can take a couple of minutes).
  open -a Docker >/dev/null 2>&1 || true
  for _ in $(seq 1 100); do
    docker_ready && break
    sleep 3
  done
fi

if ! docker_ready; then
  echo "$(date '+%Y-%m-%d %H:%M:%S') Docker daemon did not become ready after 5 minutes" >&2
  exit 1
fi

if docker inspect "$LABEL" >/dev/null 2>&1; then
  # Idempotent; also covers the case where the restart policy did not fire.
  docker start "$LABEL" >/dev/null
  echo "$(date '+%Y-%m-%d %H:%M:%S') container $LABEL is up"
  exit 0
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') container $LABEL does not exist yet;" \
  "run 'docker compose up -d' in the project once" >&2
exit 1
