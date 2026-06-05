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


def _truncate(text: str, limit: int) -> str:
    """Truncate to limit, preserving the end of the string.

    For tracebacks the most useful line is the last one (the exception type
    and message), so we keep the tail rather than the head when truncating.
    """
    if len(text) <= limit:
        return text
    keep_head = limit // 3
    keep_tail = limit - keep_head - 6  # 6 for the "\n…\n" separator
    return text[:keep_head] + "\n…\n" + text[-keep_tail:]


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
        # Include timestamp and logger name in the body so each Discord
        # message is self-contained without needing to cross-reference logs.
        self.setFormatter(logging.Formatter(
            "%(asctime)s  %(name)s\n%(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            emoji = _EMOJI.get(record.levelno, "🔔")
            # format() appends the full traceback when exc_info is set.
            body = self.format(record)
            # Reserve space for the header line and code block markers.
            header = f"{emoji} **{record.levelname}**"
            max_body = _LIMIT - len(header) - 10  # 10 for ```\n...\n```
            body = _truncate(body, max_body)
            content = f"{header}\n```\n{body}\n```"
            threading.Thread(
                target=_post,
                args=(self._url, {"content": content}),
                daemon=True,
            ).start()
        except Exception:
            pass
