import logging
from datetime import datetime, timedelta

from telegram import Update
from telegram.ext import ContextTypes

import acl as acl_store
from radarr import RadarrClient, RadarrError

logger = logging.getLogger(__name__)


def _radarr(context: ContextTypes.DEFAULT_TYPE) -> RadarrClient:
    return RadarrClient(context.application.bot_data["config"])


def _authorized(user_id: int, config: dict) -> bool:
    return acl_store.is_authorized(user_id) or user_id == config["OWNER_ID"]


async def library_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config = context.application.bot_data["config"]
    if not _authorized(update.effective_user.id, config):
        await update.message.reply_text("Unauthorized.")
        return

    query = " ".join(context.args).lower() if context.args else ""

    try:
        movies = await _radarr(context).get_library()
    except RadarrError as e:
        logger.error("Library fetch failed: %s", e)
        await update.message.reply_text(f"Failed to fetch library: {e}")
        return

    if query:
        movies = [m for m in movies if query in m.get("title", "").lower()]

    if not movies:
        msg = f"No movies matching '{query}'." if query else "Library is empty."
        await update.message.reply_text(msg)
        return

    movies.sort(key=lambda m: m.get("sortTitle") or m.get("title", ""))
    max_results = config.get("MAX_RESULTS", 15)
    displayed = movies[:max_results]

    lines = []
    for m in displayed:
        mark = "✓" if m.get("hasFile") else "✗"
        lines.append(f"{mark} {m.get('title', '?')} ({m.get('year', '?')})")

    header = f"Library — {len(movies)} movies" if not query else f"Results for '{query}' ({len(movies)})"
    if len(movies) > max_results:
        header += f", showing first {max_results}"

    await update.message.reply_text(header + ":\n\n" + "\n".join(lines))


async def upcoming_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config = context.application.bot_data["config"]
    if not _authorized(update.effective_user.id, config):
        await update.message.reply_text("Unauthorized.")
        return

    days = 30
    if context.args:
        try:
            days = int(context.args[0])
        except ValueError:
            await update.message.reply_text("Usage: /upcoming [days]")
            return

    now = datetime.utcnow()
    end = now + timedelta(days=days)

    try:
        movies = await _radarr(context).get_calendar(
            start=now.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
        )
    except RadarrError as e:
        logger.error("Calendar fetch failed: %s", e)
        await update.message.reply_text(f"Failed to fetch calendar: {e}")
        return

    if not movies:
        await update.message.reply_text(f"No upcoming releases in the next {days} days.")
        return

    lines = []
    for m in movies:
        release = m.get("digitalRelease") or m.get("physicalRelease") or m.get("inCinemas") or "?"
        if len(release) > 10:
            release = release[:10]
        lines.append(f"➸ {m.get('title', '?')} — {release}")

    await update.message.reply_text(f"Upcoming in the next {days} days:\n\n" + "\n".join(lines))
