#!/usr/bin/env bash
# Builds the image from this project and (re)creates the container.
#
#   ./deploy/start-bms.sh
#
# The image is stored locally by Docker (bms-notifier:latest) and the database
# lives in the Docker volume book-my-show-notification_bms_data, so nothing is
# copied outside the project. Re-run this after changing the code or .env.
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="bms-notifier:latest"
CONTAINER="bms-notifier"
VOLUME="book-my-show-notification_bms_data"
DATA_DIR="${BMS_DATA_DIR:-$HOME/docker/drive/bms}"
PORT="${PORT:-7654}"
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"

docker_ready() { docker info >/dev/null 2>&1; }

if ! docker_ready; then
  echo "Starting Docker..."
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

# .env is the single source of truth for runtime settings.
if [ -f "$PROJECT_DIR/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  . "$PROJECT_DIR/.env"
  set +a
fi

echo "Building $IMAGE from $PROJECT_DIR"
docker build -t "$IMAGE" "$PROJECT_DIR"

# Named volume backed by a directory on internal disk. Created once; keeps data.
mkdir -p "$DATA_DIR"
if ! docker volume inspect "$VOLUME" >/dev/null 2>&1; then
  echo "Creating volume $VOLUME -> $DATA_DIR"
  docker volume create --driver local \
    --opt type=none --opt o=bind --opt device="$DATA_DIR" "$VOLUME" >/dev/null
fi

echo "Recreating container $CONTAINER on port $PORT"
docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
docker run -d \
  --name "$CONTAINER" \
  --restart unless-stopped \
  -p "${PORT}:7654" \
  -v "${VOLUME}:/data" \
  -e BMS_DB_PATH=/data/bms.db \
  -e BMS_TIMEZONE=Asia/Kolkata \
  -e TZ=Asia/Kolkata \
  -e APP_TOKEN="${APP_TOKEN:-}" \
  -e PUSHBULLET_TOKEN="${PUSHBULLET_TOKEN:-}" \
  -e BMS_DEFAULT_INTERVAL="${BMS_DEFAULT_INTERVAL:-60}" \
  "$IMAGE" >/dev/null

echo "Waiting for health..."
for _ in $(seq 1 30); do
  if curl -fsS -m 3 "http://127.0.0.1:${PORT}/healthz" >/dev/null 2>&1; then
    echo "Up: http://localhost:${PORT}"
    exit 0
  fi
  sleep 1
done
echo "Container started but health did not respond yet; check 'docker logs $CONTAINER'" >&2
exit 1
