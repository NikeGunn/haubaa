# Hauba — One-liner Installer for Windows
# Usage: irm hauba.tech/install.ps1 | iex

function Write-Step($msg) { Write-Host "  [*] $msg" -ForegroundColor Cyan }
function Write-Info($msg) { Write-Host "  [+] $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "  [!] $msg" -ForegroundColor Yellow }
function Write-Err($msg)  { Write-Host "  [x] $msg" -ForegroundColor Red }

Write-Host ""
Write-Host "  ██╗  ██╗ █████╗ ██╗   ██╗██████╗  █████╗ " -ForegroundColor Magenta
Write-Host "  ██║  ██║██╔══██╗██║   ██║██╔══██╗██╔══██╗" -ForegroundColor Magenta
Write-Host "  ███████║███████║██║   ██║██████╔╝███████║" -ForegroundColor Cyan
Write-Host "  ██╔══██║██╔══██║██║   ██║██╔══██╗██╔══██║" -ForegroundColor Cyan
Write-Host "  ██║  ██║██║  ██║╚██████╔╝██████╔╝██║  ██║" -ForegroundColor White
Write-Host "  ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝ ╚═════╝ ╚═╝  ╚═╝" -ForegroundColor White
Write-Host ""
Write-Host "  Your AI Engineering Team" -ForegroundColor White
Write-Host "  One command. Ship products. Not prompts." -ForegroundColor DarkGray
Write-Host "  https://hauba.tech" -ForegroundColor Cyan
Write-Host ""
Write-Host "  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""

# ── Step 1: Find Python 3.11+ ────────────────────────────────────────────
Write-Step "Checking Python version..."

$pythonExe = $null
$pythonArgs = @()

$candidates = @(
    @{ Exe = "python"; Args = @() },
    @{ Exe = "python3"; Args = @() },
    @{ Exe = "py"; Args = @("-3") }
)

foreach ($c in $candidates) {
    try {
        $testArgs = $c.Args + @("-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        $ver = & $c.Exe @testArgs 2>$null
        if ($LASTEXITCODE -eq 0 -and $ver) {
            $parts = $ver.Trim().Split(".")
            $major = [int]$parts[0]
            $minor = [int]$parts[1]
            if ($major -ge 3 -and $minor -ge 11) {
                $pythonExe = $c.Exe
                $pythonArgs = $c.Args
                break
            }
        }
    } catch {
        continue
    }
}

if (-not $pythonExe) {
    Write-Err "Python 3.11+ is required."
    Write-Err "Download from: https://python.org/downloads/"
    return
}

$pyVersion = & $pythonExe @pythonArgs --version 2>&1 | Out-String
Write-Info "Found $pythonExe ($($pyVersion.Trim()))"

# ── Step 2: Install from PyPI ─────────────────────────────────────────────
Write-Host ""
Write-Step "Installing Hauba from PyPI..."

$pipArgs = $pythonArgs + @("-m", "pip", "install", "--upgrade", "hauba")
$pipOutput = & $pythonExe @pipArgs 2>&1 | Out-String
$pipExit = $LASTEXITCODE

if ($pipExit -ne 0) {
    Write-Err "Installation failed:"
    Write-Host $pipOutput -ForegroundColor Red
    Write-Err "Try manually: $pythonExe -m pip install hauba"
    return
}

$lastLine = ($pipOutput -split "`n" | Where-Object { $_.Trim() -ne "" } | Select-Object -Last 1)
if ($lastLine) { Write-Host "    $($lastLine.Trim())" -ForegroundColor DarkGray }
Write-Info "Package installed"

# ── Step 3: Verify ────────────────────────────────────────────────────────
Write-Host ""
Write-Step "Verifying installation..."

$haubaCmd = Get-Command hauba -ErrorAction SilentlyContinue
if ($haubaCmd) {
    Write-Info "hauba CLI found in PATH"

    $sdkCheck = & $pythonExe @pythonArgs -c "import copilot; print('OK')" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Info "Copilot SDK: ready"
    } else {
        Write-Warn "Copilot SDK not found (installs automatically on first run)"
    }

    Write-Host ""
    Write-Host "  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
    Write-Host ""
    Write-Host "  Installation complete!" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Get started in 30 seconds:" -ForegroundColor White
    Write-Host ""
    Write-Host "  1. " -ForegroundColor Green -NoNewline; Write-Host "hauba init" -ForegroundColor White -NoNewline; Write-Host "              # Set up your API key" -ForegroundColor DarkGray
    Write-Host "  2. " -ForegroundColor Green -NoNewline; Write-Host "hauba run ""build me a dashboard""" -ForegroundColor White
    Write-Host "                               " -NoNewline; Write-Host "# Ship your first product" -ForegroundColor DarkGray
    Write-Host "  3. " -ForegroundColor Green -NoNewline; Write-Host "hauba setup whatsapp" -ForegroundColor White -NoNewline; Write-Host "   # Get results on WhatsApp" -ForegroundColor DarkGray
    Write-Host ""
    Write-Host "  Other commands:" -ForegroundColor DarkGray
    Write-Host "    hauba status" -ForegroundColor Cyan -NoNewline; Write-Host "           # Check configuration" -ForegroundColor DarkGray
    Write-Host "    hauba doctor" -ForegroundColor Cyan -NoNewline; Write-Host "           # Diagnose issues" -ForegroundColor DarkGray
    Write-Host "    hauba serve" -ForegroundColor Cyan -NoNewline; Write-Host "            # Web dashboard" -ForegroundColor DarkGray
    Write-Host "    hauba voice" -ForegroundColor Cyan -NoNewline; Write-Host "            # Talk to your AI team" -ForegroundColor DarkGray
    Write-Host ""
    Write-Host "  Join the community: github.com/NikeGunn/haubaa" -ForegroundColor DarkGray
    Write-Host ""
} else {
    Write-Warn "Installed but 'hauba' not found in PATH."
    Write-Warn "Try: $pythonExe -m hauba --help"
    Write-Warn "Or restart your terminal and try again."
}
