#!/usr/bin/env bash
# LaunchAgent entry point. Installed to an internal-disk path because macOS
# denies launchd-spawned processes access to external volumes.
#
# Works entirely from the bundle written by deploy/start-bms.sh, so it can
# recreate the container (not just start an existing one).
set -uo pipefail

CONTAINER="bms-notifier"
BUNDLE_DIR="$HOME/Library/Application Support/bms-notifier"
COMPOSE_FILE="$BUNDLE_DIR/docker-compose.yml"
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*"; }

docker_ready() { docker info >/dev/null 2>&1; }

if ! docker_ready; then
  # Docker Desktop is not guaranteed to be up yet; start it and wait. A cold
  # start can take a couple of minutes.
  log "waiting for the Docker daemon"
  open -a Docker >/dev/null 2>&1 || true
  for _ in $(seq 1 100); do
    docker_ready && break
    sleep 3
  done
fi

if ! docker_ready; then
  log "ERROR: Docker daemon did not become ready after 5 minutes" >&2
  exit 1
fi

if [ ! -f "$COMPOSE_FILE" ]; then
  log "ERROR: no bundle at $BUNDLE_DIR; run deploy/start-bms.sh from the repo once" >&2
  exit 1
fi

# Docker Desktop can enumerate containers before the VM has restored them, so
# retry rather than trusting the first answer.
for attempt in 1 2 3 4 5; do
  # `docker container inspect` (not `docker inspect`) so a same-named image is
  # never mistaken for the container.
  if docker container inspect "$CONTAINER" >/dev/null 2>&1; then
    if docker start "$CONTAINER" >/dev/null 2>&1; then
      log "container $CONTAINER is up"
      exit 0
    fi
  else
    # Container definition is gone (e.g. Docker Desktop lost its state): rebuild
    # it from the bundle. The named volume keeps the database.
    log "container $CONTAINER not present, recreating from bundle"
    if docker compose --project-directory "$BUNDLE_DIR" -f "$COMPOSE_FILE" up -d \
        --no-build --remove-orphans >>"$BUNDLE_DIR/compose.log" 2>&1; then
      log "container $CONTAINER recreated"
      exit 0
    fi
  fi
  sleep 6
done

log "ERROR: could not bring $CONTAINER up; see $BUNDLE_DIR/compose.log" >&2
exit 1
