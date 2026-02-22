# Hauba — One-liner Installer for Windows
# Usage: irm hauba.tech/install.ps1 | iex

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

Write-Info "Installing hauba from PyPI..."

# Run pip install — capture all output, ignore stderr noise from pip
$pipArgs = $pythonArgs + @("-m", "pip", "install", "--upgrade", "hauba")
$pipOutput = & $pythonExe @pipArgs 2>&1 | Out-String
$pipExit = $LASTEXITCODE

if ($pipExit -ne 0) {
    Write-Err "Installation failed:"
    Write-Host $pipOutput -ForegroundColor Red
    Write-Err "Try manually: $pythonExe -m pip install hauba"
    return
}

# Show last meaningful line
$lastLine = ($pipOutput -split "`n" | Where-Object { $_.Trim() -ne "" } | Select-Object -Last 1)
if ($lastLine) { Write-Host "  $($lastLine.Trim())" -ForegroundColor DarkGray }

# Verify
$haubaCmd = Get-Command hauba -ErrorAction SilentlyContinue
if ($haubaCmd) {
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
    Write-Warn "Try: $pythonExe -m hauba --help"
    Write-Warn "Or restart your terminal and try again."
}
