#!/usr/bin/env bash
# Brings the notifier container up from the repo. Safe to run repeatedly.
#
# The repo may live on an external volume, which launchd cannot read, so this
# script publishes a self-contained bundle to internal disk:
#   ~/Library/Application Support/bms-notifier/docker-compose.yml
#   ~/Library/Application Support/bms-notifier/.env      (resolved values)
# deploy/autostart.sh runs that bundle at login.
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUNDLE_DIR="$HOME/Library/Application Support/bms-notifier"
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"

docker_ready() { docker info >/dev/null 2>&1; }

if ! docker_ready; then
  open -a Docker >/dev/null 2>&1 || true
  for _ in $(seq 1 100); do
    docker_ready && break
    sleep 3
  done
fi
if ! docker_ready; then
  echo "Docker daemon did not become ready after 5 minutes" >&2
  exit 1
fi

mkdir -p "$BUNDLE_DIR"
cp "$PROJECT_DIR/docker-compose.yml" "$BUNDLE_DIR/docker-compose.yml"
install -m 755 "$PROJECT_DIR/deploy/autostart.sh" "$BUNDLE_DIR/autostart.sh"

# Bake the values the container needs, with absolute paths, so the bundle never
# depends on the external drive or on launchd's environment.
env_value() {
  local key="$1" fallback="$2" value=""
  if [ -f "$PROJECT_DIR/.env" ]; then
    value="$(sed -n "s/^${key}=//p" "$PROJECT_DIR/.env" | tail -1 | tr -d '\r')"
  fi
  printf '%s' "${value:-$fallback}"
}

umask 077
cat > "$BUNDLE_DIR/.env" <<EOF
APP_TOKEN=$(env_value APP_TOKEN "")
PUSHBULLET_TOKEN=$(env_value PUSHBULLET_TOKEN "")
BMS_DEFAULT_INTERVAL=$(env_value BMS_DEFAULT_INTERVAL "60")
PORT=$(env_value PORT "7654")
BMS_DATA_DIR=${BMS_DATA_DIR:-$HOME/docker/drive/bms}
EOF

echo "Bundle written to $BUNDLE_DIR"

# Build (and run) from the repo, which has the Dockerfile and source.
cd "$PROJECT_DIR"
docker compose up -d --build --remove-orphans
