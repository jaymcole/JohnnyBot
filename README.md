# JohnnyBot

A Python-based Discord bot for remote management of a Telegram bot running on
the same server. It exposes two guild-scoped slash commands and is designed to
be self-updating and resilient to server reboots.

## Commands

- `/restart-telegram` — kills the running Telegram bot process and relaunches it.
- `/update-self` — pulls the latest code from git and restarts the Discord bot
  via the watchdog (with a syntax check so a bad push can't take the bot offline).

## Prerequisites

- Python 3.10+
- Node.js (already installed for the Telegram bot)
- git

## First-time setup

```bash
# 1. Clone the repo
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git
cd YOUR_REPO

# 2. Install Python dependencies
pip3 install -r requirements.txt

# 3. Configure environment
cp .env.example .env
nano .env  # Fill in all values

# 4. Make the watchdog executable
chmod +x run_bot.sh

# 5. Start a persistent tmux session
tmux new-session -d -s discord-bot
tmux send-keys -t discord-bot "./run_bot.sh" Enter

# 6. Detach from tmux (the bot is now running in the background)
# Press Ctrl+B then D
```

## How to get the required values

- **DISCORD_TOKEN** — Create a bot at <https://discord.com/developers/applications>, go to Bot > Token
- **DISCORD_GUILD_ID** — In Discord, enable Developer Mode (Settings > Advanced), then right-click your server and click "Copy Server ID"
- **ALLOWED_USER_IDS** — Right-click a user in Discord and click "Copy User ID". Comma-separate multiple IDs.
- **TELEGRAM_BOT_DIR** — Absolute path to the `telegram-radarr-bot` directory on the server
- **TELEGRAM_BOT_COMMAND** — `node radarr.js`
- **TELEGRAM_PID_FILE** — Recommended: `/tmp/telegram_bot.pid`

## Required Discord bot permissions

When inviting the bot to your server, it needs:

- `applications.commands` scope (for slash commands)
- `bot` scope
- **Send Messages** permission

## Attaching to the bot's tmux session (for debugging)

```bash
tmux attach -t discord-bot
```

## Reattaching after a server reboot

After a reboot, the tmux session will be gone. Re-run step 5 from the setup
instructions.
