#!/usr/bin/env bash
set -euo pipefail
DST="${HOME}/Library/LaunchAgents/com.llmxfactors.scout.discover.plist"

if [[ -f "${DST}" ]]; then
    launchctl unload "${DST}" 2>/dev/null || true
    rm "${DST}"
    echo "removed: ${DST}"
else
    echo "(nothing to remove)"
fi
