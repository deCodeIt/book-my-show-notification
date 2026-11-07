#!/usr/bin/env bash
# Removes the LaunchAgent (the container itself keeps running until stopped).
set -euo pipefail

LABEL="com.local.bms-notifier"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
RUNNER="$HOME/Library/Application Support/bms-notifier/autostart.sh"

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || launchctl unload "$PLIST" 2>/dev/null || true
rm -f "$PLIST"
rm -rf "$(dirname "$RUNNER")"
echo "Removed $PLIST and $RUNNER"
echo "The container itself is still running; stop it with 'docker compose down'."
