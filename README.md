# JohnnyBot

A Telegram bot for managing your [Radarr](https://radarr.video/) movie library —
search for movies, add them with a quality profile and root folder, browse your
library, and trigger Radarr maintenance commands, all from a Telegram chat.

This is a modern Python rewrite of
[telegram-radarr-bot](https://github.com/itsmegb/telegram-radarr-bot), built on
[python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)
v20+ and async [httpx](https://www.python-httpx.org/). It runs under a watchdog
that auto-restarts and self-updates, so transient failures (such as a Prowlarr
or Radarr service update) heal themselves instead of requiring an SSH session.

## Commands

| Command | Who | Description |
| --- | --- | --- |
| `/start` | anyone | Welcome message |
| `/help` | anyone | List commands |
| `/auth <password>` | anyone | Authorize yourself with the access password |
| `/query <title>` | users | Search for a movie and add it (guided flow) |
| `/library [query]` | users | List/search your Radarr library |
| `/upcoming [days]` | users | Upcoming releases (default: 30 days) |
| `/clear` | users | Cancel the current operation |
| `/rss` | owner | Trigger an RSS sync |
| `/wanted` | owner | Search for wanted/missing movies |
| `/refresh` | owner | Refresh the library |
| `/cid` | owner | Show the current chat ID |
| `/users` | owner | List authorized and revoked users |
| `/revoke` | owner | Revoke a user's access (guided) |
| `/unrevoke` | owner | Restore a revoked user (guided) |

The `/query` flow is conversational: search → pick a result → confirm → choose a
quality profile → choose whether to monitor → choose a root folder → choose
whether to search immediately. Send `/clear` at any point to cancel.

## How access works

- The **owner** (`OWNER_ID` in `env.json`) always has full access, including all
  admin commands.
- Anyone else must run `/auth <password>` once. Authorized user IDs are stored in
  `acl.json` (gitignored, so it never gets committed or clobbered by `git pull`).
- The owner can `/revoke` and `/unrevoke` other users.

## Prerequisites

- Python 3.10+
- A running Radarr instance with an API key (Settings → General → API Key)
- git

## First-time setup

```bash
# 1. Clone the repo
git clone https://github.com/jaymcole/JohnnyBot.git
cd JohnnyBot

# 2. Install Python dependencies
pip3 install -r requirements.txt

# 3. Configure environment
#    env.json holds all config and is gitignored, so local edits never
#    conflict with future git pulls.
cp env.json.example env.json
nano env.json   # Fill in all values

# 4. Make the watchdog executable
chmod +x run_bot.sh

# 5. Start a persistent tmux session
tmux new-session -d -s johnnybot
tmux send-keys -t johnnybot "./run_bot.sh" Enter

# 6. Detach from tmux (the bot keeps running in the background)
# Press Ctrl+B then D
```

## How to get the required values

- **TELEGRAM_BOT_TOKEN** — Message [@BotFather](https://t.me/BotFather) on
  Telegram, run `/newbot`, and copy the token it gives you.
- **OWNER_ID** — Your numeric Telegram user ID. Message
  [@userinfobot](https://t.me/userinfobot) to get it. (Chicken-and-egg note: you
  need this *before* the bot will treat you as owner, which is why an external
  bot is the easiest way to find it.)
- **BOT_PASSWORD** — Any password you choose; share it with people you want to
  grant access via `/auth`.
- **RADARR_HOST** / **RADARR_PORT** / **RADARR_API_KEY** — Your Radarr address
  and API key. The API key is under Radarr → Settings → General → Security.
- **NOTIFY_CHAT_ID** — *(optional)* The chat to send notifications to. Run `/cid`
  in the desired chat to get its ID, then put it here. Leave as `null` to
  disable notifications. See [Notifications](#notifications).

## Configuration reference

| Key | Required | Default | Description |
| --- | --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | yes | — | Bot token from BotFather |
| `BOT_PASSWORD` | yes | — | Password used by `/auth` |
| `OWNER_ID` | yes | — | Your Telegram user ID (admin) |
| `RADARR_HOST` | yes | — | Radarr hostname/IP |
| `RADARR_API_KEY` | yes | — | Radarr API key |
| `RADARR_PORT` | no | `7878` | Radarr port |
| `RADARR_SSL` | no | `false` | Use HTTPS to reach Radarr |
| `RADARR_VERIFY_SSL` | no | `true` | Verify Radarr's TLS cert (set `false` for self-signed) |
| `RADARR_URL_BASE` | no | `""` | URL base if Radarr runs under a subpath |
| `RADARR_USERNAME` | no | — | Basic-auth username, if Radarr requires it |
| `RADARR_PASSWORD` | no | — | Basic-auth password, if Radarr requires it |
| `NOTIFY_CHAT_ID` | no | `null` | Chat ID for Radarr notifications |
| `MAX_RESULTS` | no | `15` | Max items shown in search/library/upcoming lists |

## Notifications

JohnnyBot can ping a Telegram chat when Radarr grabs, imports, or otherwise acts
on a movie. This uses Radarr's **Custom Script** connection, which runs
`notify.py` on each event — no extra web server or open ports required.

1. Set `NOTIFY_CHAT_ID` in `env.json`. Run `/cid` in the chat you want notified
   to find its ID (a private chat with the bot, or a group it's in).
2. Make the script executable: `chmod +x notify.py`
3. In Radarr: **Settings → Connect → + → Custom Script**, set the Path to the
   absolute path of `notify.py`, and enable the events you care about (Grab,
   Import/Download, etc.). Use **Test** to confirm it works.

If you installed dependencies in a virtualenv, edit the shebang at the top of
`notify.py` to point at that interpreter, since Radarr runs scripts with the
system `python3`.

## Updating

`run_bot.sh` pulls the latest code on every restart, so to update you can just
restart the bot. The bot reads config from the gitignored `env.json`, so pulls
never conflict with your local settings.

## Attaching to the bot's tmux session (for debugging)

```bash
tmux attach -t johnnybot
```

## Reattaching after a server reboot

After a reboot the tmux session is gone. Re-run step 5 from the setup above.
