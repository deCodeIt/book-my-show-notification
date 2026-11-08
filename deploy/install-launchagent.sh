#!/usr/bin/env bash
# Installs a per-user LaunchAgent that brings the notifier container up at login.
#
# The whole container spec lives inside the plist as an inline `docker run`
# command: the project is not copied anywhere, the image stays in Docker's local
# store and the database stays in the bms_data volume.
#
#   ./deploy/install-launchagent.sh
#
# Re-run this after changing .env (the values are baked into the plist).
set -euo pipefail

LABEL="com.local.bms-notifier"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

# Build the image and start the container now, so the first login has nothing
# left to do but `docker start`.
bash "$PROJECT_DIR/deploy/start-bms.sh"

# Values from .env, baked into the launch command.
APP_TOKEN=""; PUSHBULLET_TOKEN=""; BMS_DEFAULT_INTERVAL="60"; PORT="7654"
if [ -f "$PROJECT_DIR/.env" ]; then
  env_value() { sed -n "s/^$1=//p" "$PROJECT_DIR/.env" | tail -1 | tr -d '\r'; }
  APP_TOKEN="$(env_value APP_TOKEN)"
  PUSHBULLET_TOKEN="$(env_value PUSHBULLET_TOKEN)"
  BMS_DEFAULT_INTERVAL="$(env_value BMS_DEFAULT_INTERVAL)"; BMS_DEFAULT_INTERVAL="${BMS_DEFAULT_INTERVAL:-60}"
  PORT="$(env_value PORT)"; PORT="${PORT:-7654}"
fi
case "$APP_TOKEN$PUSHBULLET_TOKEN" in
  *'"'*|*'\'*|*'&'*) echo "Tokens must not contain quotes, backslashes or '&'" >&2; exit 1 ;;
esac

# Template; placeholders are substituted below so the inner shell syntax is
# never expanded by this script.
read -r -d '' TEMPLATE <<'TPL' || true
set -u
export PATH=/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin
docker info >/dev/null 2>&1 || {
  open -a Docker >/dev/null 2>&1 || true
  n=0
  while [ "$n" -lt 100 ]; do
    docker info >/dev/null 2>&1 && break
    sleep 3
    n=$((n + 1))
  done
}
if ! docker info >/dev/null 2>&1; then
  echo "$(date '+%Y-%m-%d %H:%M:%S') ERROR: docker daemon unavailable" >&2
  exit 1
fi
if docker container inspect bms-notifier >/dev/null 2>&1; then
  docker start bms-notifier >/dev/null && echo "$(date '+%Y-%m-%d %H:%M:%S') started existing container"
else
  echo "$(date '+%Y-%m-%d %H:%M:%S') container missing, recreating from image"
  docker run -d \
    --name bms-notifier \
    --restart unless-stopped \
    -p __PORT__:7654 \
    -v book-my-show-notification_bms_data:/data \
    -e BMS_DB_PATH=/data/bms.db \
    -e BMS_TIMEZONE=Asia/Kolkata \
    -e TZ=Asia/Kolkata \
    -e APP_TOKEN="__APP_TOKEN__" \
    -e PUSHBULLET_TOKEN="__PUSHBULLET_TOKEN__" \
    -e BMS_DEFAULT_INTERVAL=__INTERVAL__ \
    bms-notifier:latest >/dev/null && echo "$(date '+%Y-%m-%d %H:%M:%S') container recreated"
fi
docker container inspect bms-notifier >/dev/null 2>&1
TPL

COMMAND="${TEMPLATE//__PORT__/$PORT}"
COMMAND="${COMMAND//__APP_TOKEN__/$APP_TOKEN}"
COMMAND="${COMMAND//__PUSHBULLET_TOKEN__/$PUSHBULLET_TOKEN}"
COMMAND="${COMMAND//__INTERVAL__/$BMS_DEFAULT_INTERVAL}"

xml_escape() { sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g'; }
ESCAPED_COMMAND="$(printf '%s' "$COMMAND" | xml_escape)"

mkdir -p "$HOME/Library/LaunchAgents"
umask 077
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>-c</string>
    <string>$ESCAPED_COMMAND</string>
  </array>
  <key>WorkingDirectory</key>
  <string>/tmp</string>
  <key>RunAtLoad</key>
  <true/>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
  </dict>
  <key>StandardOutPath</key>
  <string>/tmp/bms-notifier.log</string>
  <key>StandardErrorPath</key>
  <string>/tmp/bms-notifier.err</string>
</dict>
</plist>
EOF
chmod 600 "$PLIST"

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST" 2>/dev/null || launchctl load "$PLIST"

echo
echo "Installed $PLIST (mode 600 — it contains your APP_TOKEN)"
echo "Logs: /tmp/bms-notifier.log and /tmp/bms-notifier.err"
echo "UI:   http://localhost:$PORT"
