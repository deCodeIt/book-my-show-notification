#!/usr/bin/env bash
# Removes the LaunchAgent (the container itself keeps running until stopped).
set -euo pipefail

LABEL="com.local.bms-notifier"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || launchctl unload "$PLIST" 2>/dev/null || true
rm -f "$PLIST"
echo "Removed $PLIST"
