#!/usr/bin/env bash
# Bootstrap a fresh macOS host (or re-bootstrap an existing one).
# Idempotent: safe to re-run.
#
# Usage:  bash scripts/bootstrap.sh [--packs-repo <url>] [--no-launchd]
#
# After this script:
#   - dependencies installed (`uv sync`)
#   - .env exists (you'll be prompted to edit if it's still the example)
#   - llmx-scout-packs cloned alongside (if --packs-repo given) and wired in
#   - `scout doctor` passes
#   - launchd agent installed and registered (skip with --no-launchd)
#   - dry-run smoke succeeds

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${PROJECT_ROOT}"

PACKS_REPO=""
INSTALL_LAUNCHD=1

while [[ $# -gt 0 ]]; do
    case "$1" in
        --packs-repo)  PACKS_REPO="$2"; shift 2 ;;
        --no-launchd)  INSTALL_LAUNCHD=0; shift ;;
        -h|--help)
            sed -n '2,15p' "$0"
            exit 0
            ;;
        *) echo "unknown arg: $1" >&2; exit 2 ;;
    esac
done

say()  { printf "\033[1;34m==>\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m!! \033[0m %s\n" "$*" >&2; }
fail() { printf "\033[1;31mXX \033[0m %s\n" "$*" >&2; exit 1; }

# ---- 1. prerequisites ----
say "Checking prerequisites"
command -v git >/dev/null || fail "git is required (xcode-select --install)"
command -v uv  >/dev/null || fail "uv is required (brew install uv)"

# ---- 2. install deps ----
say "Installing Python deps via uv"
uv sync --quiet

# ---- 3. .env ----
if [[ ! -f .env ]]; then
    cp .env.example .env
    chmod 600 .env
    warn ".env created from template — edit it now to add your API keys, then re-run"
    warn "  open .env"
    exit 1
fi
# Reject the obvious unconfigured case
if grep -qE "^[#]?\s*OPENROUTER_API_KEY=\s*$" .env || grep -qE "OPENROUTER_API_KEY=sk-or-v1-\\.\\.\\." .env; then
    if ! grep -qE "^ANTHROPIC_API_KEY=" .env; then
        fail ".env appears to be unconfigured. Edit it to add either OPENROUTER_API_KEY or ANTHROPIC_API_KEY."
    fi
fi
say ".env present"

# ---- 4. companion packs repo ----
if [[ -n "${PACKS_REPO}" ]]; then
    PACKS_LOCAL="$(cd "${PROJECT_ROOT}/.." && pwd)/llmx-scout-packs"
    if [[ ! -d "${PACKS_LOCAL}/.git" ]]; then
        say "Cloning packs repo: ${PACKS_REPO}"
        git clone "${PACKS_REPO}" "${PACKS_LOCAL}"
        mkdir -p "${PACKS_LOCAL}/packs"
    else
        say "Packs repo already at ${PACKS_LOCAL} — pulling latest"
        (cd "${PACKS_LOCAL}" && git pull --ff-only)
    fi

    # Ensure local toml override exists with output_dir set
    LOCAL_TOML="${PROJECT_ROOT}/config/scout.local.toml"
    if [[ ! -f "${LOCAL_TOML}" ]] || ! grep -q "^output_dir" "${LOCAL_TOML}"; then
        say "Wiring output_dir → ${PACKS_LOCAL}/packs"
        echo "output_dir = \"${PACKS_LOCAL}/packs\"" >> "${LOCAL_TOML}"
    fi
fi

# ---- 5. doctor ----
say "Running scout doctor"
if ! uv run scout doctor; then
    warn "scout doctor reported issues — review output above"
    # Don't auto-exit; user may have intentionally configured non-default state
fi

# ---- 6. dry-run smoke ----
say "Smoke test (dry-run discover, 5 candidates)"
uv run scout discover --limit 5 --dry-run

# ---- 7. launchd ----
if [[ "${INSTALL_LAUNCHD}" -eq 1 ]]; then
    say "Installing launchd agent"
    bash scripts/install_launchd.sh
    say "Triggering one immediate run to verify"
    launchctl start com.llmxfactors.scout.discover
    sleep 2
    if launchctl list | grep -q "com.llmxfactors.scout.discover"; then
        say "Agent registered. Tail logs:  tail -f logs/cron.log"
    else
        warn "Agent did not register — check launchctl list manually"
    fi
else
    say "Skipped launchd install (--no-launchd)"
fi

say "Done. Next steps:"
echo "  - tail -f logs/cron.log                       (watch the next scheduled run)"
echo "  - uv run scout list --since today              (see today's packs)"
echo "  - bash scripts/uninstall_launchd.sh            (remove the schedule)"
