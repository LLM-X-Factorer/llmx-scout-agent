#!/usr/bin/env bash
# Install the scout launchd agent into ~/Library/LaunchAgents.
# Generates the actual plist from the template using values detected on
# this host (uv path, project root, HOME, PATH). Idempotent.

set -euo pipefail

PLIST_NAME="com.llmxfactors.scout.discover.plist"
TEMPLATE="$(cd "$(dirname "$0")" && pwd)/${PLIST_NAME}.template"
DST="${HOME}/Library/LaunchAgents/${PLIST_NAME}"
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if [[ ! -f "${TEMPLATE}" ]]; then
    echo "missing template: ${TEMPLATE}" >&2
    exit 1
fi

# Detect uv. Prefer Homebrew (Apple Silicon then Intel), then PATH lookup.
UV_BIN=""
for candidate in /opt/homebrew/bin/uv /usr/local/bin/uv; do
    if [[ -x "${candidate}" ]]; then
        UV_BIN="${candidate}"
        break
    fi
done
if [[ -z "${UV_BIN}" ]]; then
    UV_BIN="$(command -v uv || true)"
fi
if [[ -z "${UV_BIN}" ]]; then
    echo "could not locate 'uv' on this host. Install it first (brew install uv)." >&2
    exit 1
fi

# PATH for the launchd job: include uv's directory + standard prefixes.
UV_DIR="$(dirname "${UV_BIN}")"
LAUNCHD_PATH="${UV_DIR}:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

mkdir -p "${HOME}/Library/LaunchAgents" "${PROJECT_ROOT}/logs"

# sed substitution. Use a delimiter unlikely to appear in any path (#).
sed \
    -e "s#@@UV_BIN@@#${UV_BIN}#g" \
    -e "s#@@PROJECT_ROOT@@#${PROJECT_ROOT}#g" \
    -e "s#@@HOME@@#${HOME}#g" \
    -e "s#@@PATH@@#${LAUNCHD_PATH}#g" \
    "${TEMPLATE}" > "${DST}.tmp"

# Quick sanity: verify all placeholders got substituted.
if grep -q "@@" "${DST}.tmp"; then
    echo "template contains unresolved placeholders after substitution:" >&2
    grep "@@" "${DST}.tmp" >&2
    rm -f "${DST}.tmp"
    exit 1
fi

# Unload old version first so we pick up edits cleanly.
if launchctl list | grep -q "com.llmxfactors.scout.discover"; then
    launchctl unload "${DST}" 2>/dev/null || true
fi

mv "${DST}.tmp" "${DST}"
launchctl load "${DST}"

echo "installed: ${DST}"
echo
echo "  uv:      ${UV_BIN}"
echo "  root:    ${PROJECT_ROOT}"
echo "  home:    ${HOME}"
echo
echo "verify:    launchctl list | grep scout"
echo "trigger:   launchctl start com.llmxfactors.scout.discover"
echo "log:       tail -f ${PROJECT_ROOT}/logs/cron.log"
echo "uninstall: $(dirname "$0")/uninstall_launchd.sh"
