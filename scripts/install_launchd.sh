#!/usr/bin/env bash
# Install the scout launchd agent into ~/Library/LaunchAgents.
# Idempotent: safe to re-run.

set -euo pipefail

PLIST_NAME="com.llmxfactors.scout.discover.plist"
SRC="$(cd "$(dirname "$0")" && pwd)/${PLIST_NAME}"
DST="${HOME}/Library/LaunchAgents/${PLIST_NAME}"

if [[ ! -f "${SRC}" ]]; then
    echo "missing ${SRC}" >&2
    exit 1
fi

mkdir -p "${HOME}/Library/LaunchAgents"

# Unload first if already present, so we pick up plist edits.
if launchctl list | grep -q "com.llmxfactors.scout.discover"; then
    launchctl unload "${DST}" 2>/dev/null || true
fi

cp "${SRC}" "${DST}"
launchctl load "${DST}"

echo "installed: ${DST}"
echo
echo "verify:    launchctl list | grep scout"
echo "trigger:   launchctl start com.llmxfactors.scout.discover"
echo "log:       tail -f $(cd "$(dirname "$0")/.." && pwd)/logs/cron.log"
echo "uninstall: $(dirname "$0")/uninstall_launchd.sh"
