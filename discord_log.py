"""Discord webhook handler for bot observability.

Attaches to Python's logging system so all WARNING+ records across every
handler file are automatically shipped to Discord with zero changes to
business logic. Also exposes a send() helper for plain lifecycle messages
(startup, shutdown) that sit below WARNING but are still worth seeing.

All network calls are fire-and-forget daemon threads so a slow or dead
webhook can never block or crash the bot.
"""

import logging
import threading

import httpx

_TIMEOUT = 5.0
_LIMIT = 2000  # Discord message character limit

_EMOJI = {
    logging.WARNING: "⚠️",
    logging.ERROR: "❌",
    logging.CRITICAL: "🚨",
}


def _post(url: str, payload: dict) -> None:
    try:
        httpx.post(url, json=payload, timeout=_TIMEOUT)
    except Exception:
        pass


def send(url: str, content: str) -> None:
    """Fire-and-forget a plain text message to the webhook."""
    if not url:
        return
    if len(content) > _LIMIT:
        content = content[: _LIMIT - 1] + "…"
    threading.Thread(target=_post, args=(url, {"content": content}), daemon=True).start()


class DiscordWebhookHandler(logging.Handler):
    """Ships WARNING+ log records to a Discord webhook as formatted messages."""

    def __init__(self, url: str):
        super().__init__(level=logging.WARNING)
        self._url = url
        self.setFormatter(logging.Formatter("%(message)s"))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            emoji = _EMOJI.get(record.levelno, "🔔")
            msg = self.format(record)
            # Formatter.format() already appends the traceback when exc_info
            # is set, so no need to add it again manually.
            content = f"{emoji} **{record.levelname}** `{record.name}`\n```\n{msg}\n```"
            if len(content) > _LIMIT:
                content = content[: _LIMIT - 1] + "…"
            threading.Thread(
                target=_post,
                args=(self._url, {"content": content}),
                daemon=True,
            ).start()
        except Exception:
            pass
