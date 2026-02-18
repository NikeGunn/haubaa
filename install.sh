#!/usr/bin/env bash
# Hauba — One-liner Installer
# Usage: curl -sSL https://raw.githubusercontent.com/haubaai/hauba/main/install.sh | bash
set -euo pipefail

BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}[hauba]${NC} $1"; }
warn()  { echo -e "${YELLOW}[hauba]${NC} $1"; }
error() { echo -e "${RED}[hauba]${NC} $1" >&2; }

# Check Python 3.11+
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
    echo -e "${BOLD}Hauba — AI Agent Operating System${NC}"
    echo "Installing..."
    echo

    check_python
    info "Found $PYTHON ($($PYTHON --version))"

    # Install via pip
    info "Installing hauba from PyPI..."
    $PYTHON -m pip install --upgrade hauba

    # Verify installation
    if command -v hauba &>/dev/null; then
        info "Installation complete!"
        echo
        echo -e "${BOLD}Get started:${NC}"
        echo "  hauba init          # Set up your API key"
        echo "  hauba run \"task\"     # Run your first task"
        echo "  hauba doctor        # Check system health"
        echo
    else
        warn "Installed but 'hauba' not found in PATH."
        warn "You may need to add $($PYTHON -m site --user-base)/bin to your PATH."
    fi
}

main "$@"
