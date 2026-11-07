#!/usr/bin/env bash
# Installs a per-user LaunchAgent so the notifier comes back after login/reboot.
set -euo pipefail

LABEL="com.local.bms-notifier"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
# launchd cannot read external volumes, so the job runs from internal disk.
RUNNER="$HOME/Library/Application Support/bms-notifier/autostart.sh"

mkdir -p "$HOME/Library/LaunchAgents" "$(dirname "$RUNNER")"
chmod +x "$PROJECT_DIR/deploy/start-bms.sh" "$PROJECT_DIR/deploy/autostart.sh"
cp "$PROJECT_DIR/deploy/autostart.sh" "$RUNNER"
chmod +x "$RUNNER"

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

echo "Installed $PLIST"
echo "Runner: $RUNNER"
echo "Logs: /tmp/bms-notifier.log and /tmp/bms-notifier.err"
echo "UI:   http://localhost:7654"
