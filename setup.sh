#!/bin/bash
# First-time setup script for JohnnyBot.
# Safe to re-run: skips config prompts if env.json already exists,
# and skips the tmux launch if the session is already running.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SESSION="johnnybot"

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

if ! command -v tmux &>/dev/null; then
    err "tmux not found. Install tmux and retry."; exit 1
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
    echo "Your OWNER_ID is your numeric Telegram user ID — not your username."
    echo "If you don't know it yet, leave this as 0. Start the bot, send /myid,"
    echo "then update env.json and send /restart."
    read -rp "Owner Telegram user ID [0]: " OWNER_ID
    OWNER_ID="${OWNER_ID:-0}"

    echo ""
    read -rp "Discord webhook URL for logging (leave blank to skip): " DISCORD_WEBHOOK_URL

    # Write env.json via Python so special characters in passwords are safe.
    export _JB_TOKEN="$BOT_TOKEN"
    export _JB_PASSWORD="$BOT_PASSWORD"
    export _JB_OWNER_ID="$OWNER_ID"
    export _JB_RADARR_HOST="$RADARR_HOST"
    export _JB_RADARR_PORT="$RADARR_PORT"
    export _JB_RADARR_API_KEY="$RADARR_API_KEY"
    export _JB_DISCORD_WEBHOOK="$DISCORD_WEBHOOK_URL"
    export _JB_REPO_DIR="$REPO_DIR"

    python3 << 'PYEOF'
import json, os

cfg = {
    "TELEGRAM_BOT_TOKEN": os.environ["_JB_TOKEN"],
    "BOT_PASSWORD":        os.environ["_JB_PASSWORD"],
    "OWNER_ID":            int(os.environ["_JB_OWNER_ID"] or 0),
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
    unset _JB_TOKEN _JB_PASSWORD _JB_OWNER_ID _JB_RADARR_HOST \
          _JB_RADARR_PORT _JB_RADARR_API_KEY _JB_DISCORD_WEBHOOK _JB_REPO_DIR

    ok "env.json written."
fi

# ── Launch ────────────────────────────────────────────────────────────────────
echo ""
if tmux has-session -t "$SESSION" 2>/dev/null; then
    warn "tmux session '$SESSION' is already running."
    warn "To restart: tmux kill-session -t $SESSION && $REPO_DIR/run_bot.sh"
else
    tmux new-session -d -s "$SESSION" "$REPO_DIR/run_bot.sh"
    ok "Bot started in tmux session '$SESSION'."
fi

# ── Next steps ────────────────────────────────────────────────────────────────
echo ""
echo "=== Done ==="
echo ""
echo "View live logs:   tmux attach -t $SESSION"
echo "Detach:           Ctrl+B then D"
echo ""

OWNER_ID_VAL=$(python3 -c "import json; print(json.load(open('$REPO_DIR/env.json'))['OWNER_ID'])" 2>/dev/null || echo "0")
if [ "$OWNER_ID_VAL" = "0" ]; then
    warn "⚠  OWNER_ID is 0. Send /myid to the bot in Telegram, paste the ID"
    warn "   into env.json as OWNER_ID, then send /restart to the bot."
    echo ""
fi

echo "To enable Radarr event notifications:"
echo "  1. Send /cid to the bot in the chat you want pinged"
echo "  2. Set that number as NOTIFY_CHAT_ID in env.json"
echo "  3. In Radarr: Settings → Connect → Custom Script → $REPO_DIR/notify.py"
