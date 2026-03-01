#!/bin/sh
# Hauba — One-liner Installer
# Usage: curl -fsSL https://hauba.tech/install.sh | sh
set -eu

# ── Colors & helpers ──────────────────────────────────────────────────────
BOLD='\033[1m'
DIM='\033[2m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
WHITE='\033[1;37m'
NC='\033[0m'

info()  { printf "${GREEN}  [+]${NC} %s\n" "$1"; }
warn()  { printf "${YELLOW}  [!]${NC} %s\n" "$1"; }
err()   { printf "${RED}  [x]${NC} %s\n" "$1" >&2; }
step()  { printf "${CYAN}  [*]${NC} ${BOLD}%s${NC}\n" "$1"; }

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
    printf "${MAGENTA}  ██╗  ██╗ █████╗ ██╗   ██╗██████╗  █████╗ ${NC}\n"
    printf "${MAGENTA}  ██║  ██║██╔══██╗██║   ██║██╔══██╗██╔══██╗${NC}\n"
    printf "${CYAN}  ███████║███████║██║   ██║██████╔╝███████║${NC}\n"
    printf "${CYAN}  ██╔══██║██╔══██║██║   ██║██╔══██╗██╔══██║${NC}\n"
    printf "${WHITE}  ██║  ██║██║  ██║╚██████╔╝██████╔╝██║  ██║${NC}\n"
    printf "${WHITE}  ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝ ╚═════╝ ╚═╝  ╚═╝${NC}\n"
    printf "\n"
    printf "${BOLD}  Your AI Engineering Team${NC}\n"
    printf "${DIM}  One command. Ship products. Not prompts.${NC}\n"
    printf "${CYAN}  https://hauba.tech${NC}\n"
    printf "\n"
    printf "${DIM}  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
    printf "\n"

    # Step 1: Check Python
    step "Checking Python version..."
    check_python
    py_ver=$($PYTHON --version 2>&1)
    info "Found $PYTHON ($py_ver)"

    # Step 2: Install from PyPI
    printf "\n"
    step "Installing Hauba from PyPI..."
    $PYTHON -m pip install --upgrade hauba 2>&1 | tail -1
    info "Package installed"

    # Step 3: Verify
    printf "\n"
    step "Verifying installation..."

    if command -v hauba > /dev/null 2>&1; then
        info "hauba CLI found in PATH"

        if $PYTHON -c "import copilot; print('OK')" > /dev/null 2>&1; then
            info "Copilot SDK: ready"
        else
            warn "Copilot SDK not found (installs automatically on first run)"
        fi

        printf "\n"
        printf "${DIM}  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
        printf "\n"
        printf "${GREEN}${BOLD}  Installation complete!${NC}\n"
        printf "\n"
        printf "${BOLD}  Get started in 30 seconds:${NC}\n"
        printf "\n"
        printf "  ${GREEN}1.${NC} ${BOLD}hauba init${NC}              ${DIM}# Set up your API key${NC}\n"
        printf "  ${GREEN}2.${NC} ${BOLD}hauba run \"build me a dashboard\"${NC}\n"
        printf "                               ${DIM}# Ship your first product${NC}\n"
        printf "  ${GREEN}3.${NC} ${BOLD}hauba setup whatsapp${NC}   ${DIM}# Get results on WhatsApp${NC}\n"
        printf "\n"
        printf "${DIM}  Other commands:${NC}\n"
        printf "    ${CYAN}hauba status${NC}           ${DIM}# Check configuration${NC}\n"
        printf "    ${CYAN}hauba doctor${NC}           ${DIM}# Diagnose issues${NC}\n"
        printf "    ${CYAN}hauba serve${NC}            ${DIM}# Web dashboard${NC}\n"
        printf "    ${CYAN}hauba voice${NC}            ${DIM}# Talk to your AI team${NC}\n"
        printf "\n"
        printf "${DIM}  Join the community: ${CYAN}github.com/NikeGunn/haubaa${NC}\n"
        printf "\n"
    else
        warn "Installed but 'hauba' not found in PATH."
        warn "Try: $PYTHON -m hauba --help"
        user_base=$($PYTHON -m site --user-base 2>/dev/null || echo "\$HOME/.local")
        warn "Or add $user_base/bin to your PATH."
    fi
}

main "$@"
