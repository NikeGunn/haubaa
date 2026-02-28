#!/bin/sh
# Hauba — One-liner Installer
# Usage: curl -fsSL https://hauba.tech/install.sh | sh
set -eu

BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { printf "${GREEN}[hauba]${NC} %s\n" "$1"; }
warn()  { printf "${YELLOW}[hauba]${NC} %s\n" "$1"; }
err()   { printf "${RED}[hauba]${NC} %s\n" "$1" >&2; }

PYTHON=""

check_python() {
    for cmd in python3 python; do
        if command -v "$cmd" > /dev/null 2>&1; then
            ver=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null) || continue
            major=$(echo "$ver" | cut -d. -f1)
            minor=$(echo "$ver" | cut -d. -f2)
            if [ "$major" -ge 3 ] && [ "$minor" -ge 11 ]; then
                PYTHON="$cmd"
                return 0
            fi
        fi
    done
    err "Python 3.11+ is required. Install from https://python.org/downloads/"
    exit 1
}

main() {
    printf "\n"
    printf "${CYAN}  _   _                 _           ${NC}\n"
    printf "${CYAN} | | | |  __ _  _   _  | |__    __ _ ${NC}\n"
    printf "${CYAN} | |_| | / _\` || | | | | '_ \\\\  / _\` |${NC}\n"
    printf "${CYAN} |  _  || (_| || |_| | | |_) || (_| |${NC}\n"
    printf "${CYAN} |_| |_| \\\\__,_| \\\\__,_| |_.__/  \\\\__,_|${NC}\n"
    printf "\n"
    printf "${BOLD}  AI Workstation${NC}\n"
    printf "  ${CYAN}https://hauba.tech${NC}\n"
    printf "\n"

    check_python
    py_ver=$($PYTHON --version 2>&1)
    info "Found $PYTHON ($py_ver)"

    info "Installing hauba from PyPI..."
    $PYTHON -m pip install --upgrade hauba 2>&1 | tail -1

    if command -v hauba > /dev/null 2>&1; then
        # Verify Copilot SDK
        if $PYTHON -c "import copilot; print('OK')" > /dev/null 2>&1; then
            info "Copilot SDK: OK"
        else
            warn "Copilot SDK check inconclusive (will work on first run)"
        fi

        printf "\n"
        info "Installation complete!"
        printf "\n"
        printf "${BOLD}Get started:${NC}\n"
        printf "  ${GREEN}hauba init${NC}          # Set up your API key\n"
        printf "  ${GREEN}hauba run \"task\"${NC}     # Run your first task\n"
        printf "  ${GREEN}hauba doctor${NC}        # Check system health\n"
        printf "\n"
    else
        warn "Installed but 'hauba' not found in PATH."
        warn "Try: $PYTHON -m hauba --help"
        user_base=$($PYTHON -m site --user-base 2>/dev/null || echo "\$HOME/.local")
        warn "Or add $user_base/bin to your PATH."
    fi
}

main "$@"
