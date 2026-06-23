#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# run.sh — Bootstrap and run macshift
#
# Usage:
#   ./run.sh              Show help
#   ./run.sh doctor       Run the hardware probe
#   ./run.sh run           Rotate MAC (default 1h cadence)
#   ./run.sh run --once   Single rotation then exit
#   ./run.sh <any args>   Passed straight to macshift
#
# The script will:
#   1. Create a venv (if needed) in .venv/
#   2. Install macshift + deps into it
#   3. Forward all arguments to the macshift CLI
#
# Commands that change network settings (run, restore) need
# sudo. The script will re-exec itself with sudo when needed.
# ──────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
PYTHON="${VENV_DIR}/bin/python"
PIP="${VENV_DIR}/bin/pip"

# ── Colours ──────────────────────────────────────────────────
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Colour

info()  { printf "${CYAN}[macshift]${NC} %s\n" "$*"; }
ok()    { printf "${GREEN}[macshift]${NC} %s\n" "$*"; }
warn()  { printf "${YELLOW}[macshift]${NC} %s\n" "$*"; }
err()   { printf "${RED}[macshift]${NC} %s\n" "$*" >&2; }

# ── 1. Ensure Python 3 is available ─────────────────────────
if ! command -v python3 &>/dev/null; then
    err "Python 3 is required but not found."
    err "Install it with:  brew install python"
    exit 1
fi

# ── 2. Create venv if missing ────────────────────────────────
if [ ! -d "$VENV_DIR" ]; then
    info "Creating virtual environment in .venv/ ..."
    python3 -m venv "$VENV_DIR"
    ok "Virtual environment created."
fi

# ── 3. Install macshift (editable) if not already installed ──
if ! "$PYTHON" -c "import macshift" &>/dev/null; then
    info "Installing macshift and dependencies ..."
    "$PIP" install --upgrade pip --quiet
    "$PIP" install -e "$SCRIPT_DIR" --quiet
    ok "macshift installed successfully."
else
    # Ensure editable install is up-to-date
    "$PIP" install -e "$SCRIPT_DIR" --quiet 2>/dev/null || true
fi

# ── 4. Handle sudo for privileged commands ───────────────────
NEEDS_SUDO_CMDS=("run" "restore")
needs_sudo=false
for cmd in "${NEEDS_SUDO_CMDS[@]}"; do
    if [[ "${1:-}" == "$cmd" ]]; then
        needs_sudo=true
        break
    fi
done

if $needs_sudo && [ "$EUID" -ne 0 ]; then
    warn "The '${1}' command requires root privileges. Re-running with sudo ..."
    exec sudo "$PYTHON" -m macshift "$@"
fi

# ── 5. Run macshift ─────────────────────────────────────────
if [ $# -eq 0 ]; then
    "$PYTHON" -m macshift --help
else
    "$PYTHON" -m macshift "$@"
fi
