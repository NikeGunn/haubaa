# Hauba — One-liner Installer for Windows
# Usage: irm hauba.tech/install.ps1 | iex
$ErrorActionPreference = "Stop"

function Write-Info($msg) { Write-Host "[hauba] $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "[hauba] $msg" -ForegroundColor Yellow }
function Write-Err($msg)  { Write-Host "[hauba] $msg" -ForegroundColor Red }

Write-Host ""
Write-Host "  _   _                 _           " -ForegroundColor Cyan
Write-Host " | | | |  __ _  _   _  | |__    __ _ " -ForegroundColor Cyan
Write-Host " | |_| | / _`` || | | | | '_ \  / _`` |" -ForegroundColor Cyan
Write-Host " |  _  || (_| || |_| | | |_) || (_| |" -ForegroundColor Cyan
Write-Host " |_| |_| \__,_| \__,_| |_.__/  \__,_|" -ForegroundColor Cyan
Write-Host ""
Write-Host "  AI Agent Operating System" -ForegroundColor White
Write-Host "  https://hauba.tech" -ForegroundColor Cyan
Write-Host ""

# Find Python 3.11+
$python = $null
foreach ($cmd in @("python", "python3", "py -3")) {
    try {
        $ver = & ($cmd.Split(" ")[0]) ($cmd.Split(" ") | Select-Object -Skip 1) -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
        if ($ver) {
            $parts = $ver.Split(".")
            $major = [int]$parts[0]
            $minor = [int]$parts[1]
            if ($major -ge 3 -and $minor -ge 11) {
                $python = $cmd
                break
            }
        }
    } catch {
        continue
    }
}

if (-not $python) {
    Write-Err "Python 3.11+ is required."
    Write-Err "Download from: https://python.org/downloads/"
    exit 1
}

$pyVersion = & ($python.Split(" ")[0]) ($python.Split(" ") | Select-Object -Skip 1) --version 2>&1
Write-Info "Found $python ($pyVersion)"

Write-Info "Installing hauba from PyPI..."
& ($python.Split(" ")[0]) ($python.Split(" ") | Select-Object -Skip 1) -m pip install --upgrade hauba 2>&1 | Select-Object -Last 1

# Verify
$haubaPath = Get-Command hauba -ErrorAction SilentlyContinue
if ($haubaPath) {
    Write-Host ""
    Write-Info "Installation complete!"
    Write-Host ""
    Write-Host "Get started:" -ForegroundColor White
    Write-Host "  hauba init          " -ForegroundColor Green -NoNewline; Write-Host "# Set up your API key"
    Write-Host "  hauba run ""task""     " -ForegroundColor Green -NoNewline; Write-Host "# Run your first task"
    Write-Host "  hauba doctor        " -ForegroundColor Green -NoNewline; Write-Host "# Check system health"
    Write-Host ""
} else {
    Write-Warn "Installed but 'hauba' not found in PATH."
    Write-Warn "Try: $python -m hauba --help"
    Write-Warn "Or restart your terminal."
}
