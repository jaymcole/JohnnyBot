# First-time setup for JohnnyBot on Windows (testing/debugging only).
#
# Windows is intended purely for local testing — there is no supervisor,
# no auto-start, and no watchdog. This script installs dependencies and
# writes env.json, then you run the bot in the foreground with:
#     python bot.py
#
# Safe to re-run: skips configuration if env.json already exists.
#
# If you hit an execution-policy error, run it like this:
#     powershell -ExecutionPolicy Bypass -File .\setup.ps1

$ErrorActionPreference = "Stop"
$RepoDir = Split-Path -Parent $MyInvocation.MyCommand.Path

function Write-Err  { param($m) Write-Host "ERROR: $m" -ForegroundColor Red }
function Write-Warn { param($m) Write-Host $m -ForegroundColor Yellow }
function Write-Ok   { param($m) Write-Host $m -ForegroundColor Green }

Write-Host "=== JohnnyBot Setup (Windows / debug) ==="
Write-Host ""

# --- Prerequisites -----------------------------------------------------------
$python = (Get-Command python -ErrorAction SilentlyContinue)
if (-not $python) {
    Write-Err "python not found on PATH. Install Python 3.10+ (and check 'Add to PATH') and retry."
    exit 1
}
$verOk = (python -c "import sys; print(sys.version_info >= (3,10))").Trim()
if ($verOk -ne "True") {
    Write-Err "Python 3.10+ required (found $(python --version))."
    exit 1
}

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Err "git not found on PATH."
    exit 1
}

# --- Dependencies ------------------------------------------------------------
Write-Host "Installing Python dependencies..."
python -m pip install -q -r (Join-Path $RepoDir "requirements.txt")
Write-Ok "Dependencies installed."
Write-Host ""

# --- Configuration -----------------------------------------------------------
$envPath = Join-Path $RepoDir "env.json"
if (Test-Path $envPath) {
    Write-Warn "env.json already exists - skipping configuration. Edit it manually if needed."
} else {
    Write-Host "=== Configuration ==="
    Write-Host "Press Enter to accept a [default] value."
    Write-Host ""

    $BotToken = Read-Host "Telegram bot token (from @BotFather)"
    if ([string]::IsNullOrWhiteSpace($BotToken)) { Write-Err "Bot token is required."; exit 1 }

    $BotPassword = Read-Host "Bot access password (shared with users via /auth)"
    if ([string]::IsNullOrWhiteSpace($BotPassword)) { Write-Err "Bot password is required."; exit 1 }

    $RadarrHost = Read-Host "Radarr host [localhost]"
    if ([string]::IsNullOrWhiteSpace($RadarrHost)) { $RadarrHost = "localhost" }

    $RadarrPort = Read-Host "Radarr port [7878]"
    if ([string]::IsNullOrWhiteSpace($RadarrPort)) { $RadarrPort = "7878" }

    $RadarrApiKey = Read-Host "Radarr API key"
    if ([string]::IsNullOrWhiteSpace($RadarrApiKey)) { Write-Err "Radarr API key is required."; exit 1 }

    Write-Host ""
    Write-Host "OWNER_IDS: numeric Telegram user IDs with admin access (comma-separated)."
    Write-Host "If you don't know yours yet, leave this as 0. Start the bot, send /myid,"
    Write-Host "then update OWNER_IDS in env.json and restart."
    $OwnerIdsRaw = Read-Host "Owner Telegram user ID(s) [0]"
    if ([string]::IsNullOrWhiteSpace($OwnerIdsRaw)) { $OwnerIdsRaw = "0" }
    $OwnerIds = @($OwnerIdsRaw -split "," | ForEach-Object { $_.Trim() } | Where-Object { $_ } | ForEach-Object { [int]$_ })

    Write-Host ""
    $DiscordWebhook = Read-Host "Discord webhook URL for logging (leave blank to skip)"
    if ($null -eq $DiscordWebhook) { $DiscordWebhook = "" }

    $cfg = [ordered]@{
        TELEGRAM_BOT_TOKEN = $BotToken
        BOT_PASSWORD       = $BotPassword
        OWNER_IDS          = $OwnerIds
        NOTIFY_CHAT_ID     = $null
        DISCORD_WEBHOOK_URL = $DiscordWebhook
        MAX_RESULTS        = 15
        RADARR_HOST        = $RadarrHost
        RADARR_PORT        = [int]$RadarrPort
        RADARR_API_KEY     = $RadarrApiKey
        RADARR_SSL         = $false
        RADARR_VERIFY_SSL  = $true
        RADARR_URL_BASE    = ""
        RADARR_USERNAME    = ""
        RADARR_PASSWORD    = ""
    }

    # ConvertTo-Json renders a single-element array as a scalar; -AsArray and the
    # @() wrapper above keep OWNER_IDS a JSON list. Write UTF-8 without BOM so
    # Python's json.load reads it cleanly.
    $json = $cfg | ConvertTo-Json -Depth 5
    [System.IO.File]::WriteAllText($envPath, $json + "`n", (New-Object System.Text.UTF8Encoding($false)))
    Write-Ok "env.json written."
}

# --- Next steps --------------------------------------------------------------
Write-Host ""
Write-Host "=== Done ==="
Write-Host ""
Write-Host "Run the bot in the foreground (Ctrl+C to stop):"
Write-Host "    python bot.py"
Write-Host ""

$ownerIdsVal = "[0]"
try {
    $ownerIdsVal = (python -c "import json; print(json.load(open('env.json'))['OWNER_IDS'])").Trim()
} catch {}
if ($ownerIdsVal -eq "[0]") {
    Write-Warn "WARNING: OWNER_IDS is [0]. Send /myid to the bot in Telegram, paste the ID"
    Write-Warn "         into env.json as OWNER_IDS (e.g. [123456789]), then restart the bot."
    Write-Host ""
}

$launch = Read-Host "Start the bot now in the foreground? [Y/n]"
if ([string]::IsNullOrWhiteSpace($launch) -or $launch -match "^[Yy]") {
    Set-Location $RepoDir
    python bot.py
}
