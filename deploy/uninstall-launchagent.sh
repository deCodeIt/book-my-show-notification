#!/usr/bin/env bash
# Removes the LaunchAgent. The container keeps running until you stop it.
set -euo pipefail

LABEL="com.local.bms-notifier"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || launchctl unload "$PLIST" 2>/dev/null || true
rm -f "$PLIST"
echo "Removed $PLIST"
echo "The container is still running; stop it with: docker rm -f bms-notifier"
