#!/usr/bin/env python3
"""Standalone notifier invoked by Radarr's Custom Script connection.

Radarr runs this script when events occur (Grab, Import, etc.), passing the
event details via environment variables. The script reads them and sends a
Telegram message to NOTIFY_CHAT_ID using the same bot token as JohnnyBot.

Configure in Radarr:
  Settings -> Connect -> + -> Custom Script
  Path: /absolute/path/to/JohnnyBot/notify.py

Set NOTIFY_CHAT_ID in env.json to the chat you want pinged (use /cid in that
chat to find its ID). If NOTIFY_CHAT_ID is unset, this script does nothing.

Radarr runs custom scripts with the system python3. If you installed
dependencies in a virtualenv, change the shebang above to that interpreter,
e.g. #!/path/to/venv/bin/python3
"""

import os
import sys

import httpx

from config import load_config

TIMEOUT = 15.0


def _send(token: str, chat_id: int, text: str) -> None:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    resp = httpx.post(url, json={"chat_id": chat_id, "text": text}, timeout=TIMEOUT)
    resp.raise_for_status()


def build_message() -> str:
    event = os.environ.get("radarr_eventtype", "Unknown")
    title = os.environ.get("radarr_movie_title", "?")
    year = os.environ.get("radarr_movie_year", "")
    label = f"{title} ({year})" if year else title

    if event == "Test":
        return "JohnnyBot notification test — it works."
    if event == "Grab":
        quality = os.environ.get("radarr_release_quality", "")
        return f"🎯 Grabbed: {label}" + (f" [{quality}]" if quality else "")
    if event == "Download":
        quality = os.environ.get("radarr_moviefile_quality", "")
        upgrade = os.environ.get("radarr_isupgrade", "False") == "True"
        verb = "⬆️ Upgraded" if upgrade else "✅ Imported"
        return f"{verb}: {label}" + (f" [{quality}]" if quality else "")
    if event == "MovieAdded":
        return f"➕ Added to library: {label}"
    if event in ("MovieDelete", "MovieFileDelete"):
        return f"🗑️ Removed: {label}"
    if event == "HealthIssue":
        message = os.environ.get("radarr_health_issue_message", "")
        return f"⚠️ Radarr health issue: {message}"
    # Fallback for any event type not handled above.
    return f"Radarr event: {event} — {label}"


def main() -> None:
    config = load_config()
    chat_id = config.get("NOTIFY_CHAT_ID")
    if not chat_id:
        print("NOTIFY_CHAT_ID not set in env.json; nothing to do.")
        return
    try:
        _send(config["TELEGRAM_BOT_TOKEN"], chat_id, build_message())
    except Exception as e:
        print(f"Failed to send notification: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
