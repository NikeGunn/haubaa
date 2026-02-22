#!/usr/bin/env bash
# Hauba — One-liner Installer
# Usage: curl -fsSL https://hauba.tech/install.sh | sh
set -euo pipefail

BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${GREEN}[hauba]${NC} $1"; }
warn()  { echo -e "${YELLOW}[hauba]${NC} $1"; }
error() { echo -e "${RED}[hauba]${NC} $1" >&2; }

PYTHON=""

check_python() {
    for cmd in python3 python; do
        if command -v "$cmd" &>/dev/null; then
            local ver
            ver=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null)
            local major minor
            major=$(echo "$ver" | cut -d. -f1)
            minor=$(echo "$ver" | cut -d. -f2)
            if [ "$major" -ge 3 ] && [ "$minor" -ge 11 ]; then
                PYTHON="$cmd"
                return 0
            fi
        fi
    done
    error "Python 3.11+ is required. Install from https://python.org/downloads/"
    exit 1
}

main() {
    echo ""
    echo -e "${CYAN}  _   _                 _           ${NC}"
    echo -e "${CYAN} | | | |  __ _  _   _  | |__    __ _ ${NC}"
    echo -e "${CYAN} | |_| | / _\` || | | | | '_ \\  / _\` |${NC}"
    echo -e "${CYAN} |  _  || (_| || |_| | | |_) || (_| |${NC}"
    echo -e "${CYAN} |_| |_| \\__,_| \\__,_| |_.__/  \\__,_|${NC}"
    echo ""
    echo -e "${BOLD}  AI Agent Operating System${NC}"
    echo -e "  ${CYAN}https://hauba.tech${NC}"
    echo ""

    check_python
    info "Found $PYTHON ($($PYTHON --version 2>&1))"

    info "Installing hauba from PyPI..."
    $PYTHON -m pip install --upgrade hauba 2>&1 | tail -1

    if command -v hauba &>/dev/null; then
        echo ""
        info "Installation complete!"
        echo ""
        echo -e "${BOLD}Get started:${NC}"
        echo -e "  ${GREEN}hauba init${NC}          # Set up your API key"
        echo -e "  ${GREEN}hauba run \"task\"${NC}     # Run your first task"
        echo -e "  ${GREEN}hauba doctor${NC}        # Check system health"
        echo ""
    else
        warn "Installed but 'hauba' not found in PATH."
        warn "Try: $PYTHON -m hauba --help"
        warn "Or add $($PYTHON -m site --user-base)/bin to your PATH."
    fi
}

main "$@"
