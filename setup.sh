#!/bin/bash
# First-time setup script for JohnnyBot.
# Safe to re-run: skips config prompts if env.json already exists,
# and skips the launch step if the bot is already running.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SESSION="johnnybot"
SERVICE_NAME="johnnybot"
LAUNCHED=false

# ── Colours ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'; RESET='\033[0m'
err()  { echo -e "${RED}ERROR: $*${RESET}" >&2; }
warn() { echo -e "${YELLOW}$*${RESET}"; }
ok()   { echo -e "${GREEN}$*${RESET}"; }

echo "=== JohnnyBot Setup ==="
echo ""

# ── Prerequisites ─────────────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
    err "python3 not found. Install Python 3.10+ and retry."; exit 1
fi
py_ok=$(python3 -c "import sys; print(sys.version_info >= (3,10))")
if [ "$py_ok" != "True" ]; then
    err "Python 3.10+ required (found $(python3 --version))."; exit 1
fi

if ! command -v git &>/dev/null; then
    err "git not found."; exit 1
fi

# ── Dependencies ──────────────────────────────────────────────────────────────
echo "Installing Python dependencies..."
pip3 install -q -r "$REPO_DIR/requirements.txt"
ok "Dependencies installed."
echo ""

# ── Permissions ───────────────────────────────────────────────────────────────
chmod +x "$REPO_DIR/run_bot.sh" "$REPO_DIR/notify.py"

# ── Configuration ─────────────────────────────────────────────────────────────
if [ -f "$REPO_DIR/env.json" ]; then
    warn "env.json already exists — skipping configuration. Edit it manually if needed."
else
    echo "=== Configuration ==="
    echo "Press Enter to accept a [default] value."
    echo ""

    read -rp "Telegram bot token (from @BotFather): " BOT_TOKEN
    [ -z "$BOT_TOKEN" ] && { err "Bot token is required."; exit 1; }

    read -rp "Bot access password (shared with users via /auth): " BOT_PASSWORD
    [ -z "$BOT_PASSWORD" ] && { err "Bot password is required."; exit 1; }

    read -rp "Radarr host [localhost]: " RADARR_HOST
    RADARR_HOST="${RADARR_HOST:-localhost}"

    read -rp "Radarr port [7878]: " RADARR_PORT
    RADARR_PORT="${RADARR_PORT:-7878}"

    read -rp "Radarr API key: " RADARR_API_KEY
    [ -z "$RADARR_API_KEY" ] && { err "Radarr API key is required."; exit 1; }

    echo ""
    echo "OWNER_IDS: numeric Telegram user IDs with admin access (comma-separated)."
    echo "If you don't know yours yet, leave this as 0. Start the bot, send /myid,"
    echo "then update OWNER_IDS in env.json and send /restart."
    read -rp "Owner Telegram user ID(s) [0]: " OWNER_IDS_RAW
    OWNER_IDS_RAW="${OWNER_IDS_RAW:-0}"

    echo ""
    read -rp "Discord webhook URL for logging (leave blank to skip): " DISCORD_WEBHOOK_URL

    # Write env.json via Python so special characters in passwords are safe.
    export _JB_TOKEN="$BOT_TOKEN"
    export _JB_PASSWORD="$BOT_PASSWORD"
    export _JB_OWNER_IDS="$OWNER_IDS_RAW"
    export _JB_RADARR_HOST="$RADARR_HOST"
    export _JB_RADARR_PORT="$RADARR_PORT"
    export _JB_RADARR_API_KEY="$RADARR_API_KEY"
    export _JB_DISCORD_WEBHOOK="$DISCORD_WEBHOOK_URL"
    export _JB_REPO_DIR="$REPO_DIR"

    python3 << 'PYEOF'
import json, os

raw = os.environ["_JB_OWNER_IDS"]
owner_ids = [int(x.strip()) for x in raw.split(",") if x.strip()]

cfg = {
    "TELEGRAM_BOT_TOKEN": os.environ["_JB_TOKEN"],
    "BOT_PASSWORD":        os.environ["_JB_PASSWORD"],
    "OWNER_IDS":           owner_ids,
    "NOTIFY_CHAT_ID":      None,
    "DISCORD_WEBHOOK_URL": os.environ["_JB_DISCORD_WEBHOOK"],
    "MAX_RESULTS":         15,
    "RADARR_HOST":         os.environ["_JB_RADARR_HOST"],
    "RADARR_PORT":         int(os.environ["_JB_RADARR_PORT"]),
    "RADARR_API_KEY":      os.environ["_JB_RADARR_API_KEY"],
    "RADARR_SSL":          False,
    "RADARR_VERIFY_SSL":   True,
    "RADARR_URL_BASE":     "",
    "RADARR_USERNAME":     "",
    "RADARR_PASSWORD":     "",
}
path = os.path.join(os.environ["_JB_REPO_DIR"], "env.json")
with open(path, "w") as f:
    json.dump(cfg, f, indent=2)
    f.write("\n")
PYEOF

    # Clean up exported vars
    unset _JB_TOKEN _JB_PASSWORD _JB_OWNER_IDS _JB_RADARR_HOST \
          _JB_RADARR_PORT _JB_RADARR_API_KEY _JB_DISCORD_WEBHOOK _JB_REPO_DIR

    ok "env.json written."
fi

# ── Launch ────────────────────────────────────────────────────────────────────
echo ""

# Prefer systemd on Linux — it handles boot startup automatically.
if [ "$(uname -s)" = "Linux" ] && command -v systemctl &>/dev/null; then
    if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
        warn "Systemd service '$SERVICE_NAME' is already running."
        LAUNCHED=true
    else
        read -rp "Install systemd service for automatic start on boot? [Y/n]: " USE_SYSTEMD
        USE_SYSTEMD="${USE_SYSTEMD:-y}"
        if [[ "$USE_SYSTEMD" =~ ^[Yy]$ ]]; then
            cat > /tmp/johnnybot.service << EOF
[Unit]
Description=JohnnyBot Telegram Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$(whoami)
WorkingDirectory=$REPO_DIR
ExecStart=$REPO_DIR/run_bot.sh
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
            sudo cp /tmp/johnnybot.service /etc/systemd/system/johnnybot.service
            rm /tmp/johnnybot.service
            sudo systemctl daemon-reload
            sudo systemctl enable "$SERVICE_NAME"
            sudo systemctl start "$SERVICE_NAME"
            ok "Systemd service installed, enabled, and started."
            ok "Bot will now start automatically on every boot."
            LAUNCHED=true
        fi
    fi
fi

# Fall back to tmux if systemd was skipped or unavailable.
if [ "$LAUNCHED" = false ]; then
    if ! command -v tmux &>/dev/null; then
        err "tmux not found. Install tmux and retry, or choose systemd above."; exit 1
    fi
    if tmux has-session -t "$SESSION" 2>/dev/null; then
        warn "tmux session '$SESSION' is already running."
        warn "To restart: tmux kill-session -t $SESSION && $REPO_DIR/run_bot.sh"
    else
        tmux new-session -d -s "$SESSION" "$REPO_DIR/run_bot.sh"
        ok "Bot started in tmux session '$SESSION'."
        warn "Note: tmux session will not survive a server reboot."
        warn "Re-run setup and choose the systemd option to fix this."
    fi
    LAUNCHED=true
fi

# ── Next steps ────────────────────────────────────────────────────────────────
echo ""
echo "=== Done ==="
echo ""

if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
    echo "Bot status:     sudo systemctl status $SERVICE_NAME"
    echo "Live logs:      sudo journalctl -u $SERVICE_NAME -f"
    echo "Stop/start:     sudo systemctl stop/start $SERVICE_NAME"
else
    echo "View live logs: tmux attach -t $SESSION"
    echo "Detach:         Ctrl+B then D"
fi
echo ""

OWNER_IDS_VAL=$(python3 -c "import json; ids=json.load(open('$REPO_DIR/env.json'))['OWNER_IDS']; print(ids)" 2>/dev/null || echo "[0]")
if [ "$OWNER_IDS_VAL" = "[0]" ]; then
    warn "⚠  OWNER_IDS is [0]. Send /myid to the bot in Telegram, paste the ID"
    warn "   into env.json as OWNER_IDS (e.g. [123456789]), then send /restart."
    echo ""
fi

echo "To enable Radarr event notifications:"
echo "  1. Send /cid to the bot in the chat you want pinged"
echo "  2. Set that number as NOTIFY_CHAT_ID in env.json"
echo "  3. In Radarr: Settings → Connect → Custom Script → $REPO_DIR/notify.py"
