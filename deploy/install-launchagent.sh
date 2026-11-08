#!/usr/bin/env bash
# Installs the macOS autostart agent and publishes the internal-disk bundle.
# Safe to re-run after changing docker-compose.yml or .env.
set -euo pipefail

LABEL="com.local.bms-notifier"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
BUNDLE_DIR="$HOME/Library/Application Support/bms-notifier"
RUNNER="$BUNDLE_DIR/autostart.sh"

chmod +x "$PROJECT_DIR"/deploy/*.sh

# Publish the bundle (compose file + resolved env) and start the container.
# The bundle lives on internal disk because launchd cannot read external volumes.
bash "$PROJECT_DIR/deploy/start-bms.sh"

mkdir -p "$HOME/Library/LaunchAgents"

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
    <string>$RUNNER</string>
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

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST" 2>/dev/null || launchctl load "$PLIST"

echo
echo "Installed $PLIST"
echo "Bundle:  $BUNDLE_DIR (compose file + .env, internal disk)"
echo "Logs:    /tmp/bms-notifier.log and /tmp/bms-notifier.err"
echo "UI:      http://localhost:7654"
