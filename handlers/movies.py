import logging

from telegram import Update
from telegram.ext import (
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

import acl as acl_store
from radarr import RadarrClient, RadarrError

logger = logging.getLogger(__name__)

MOVIE_SELECT, CONFIRM, PROFILE_SELECT, MONITOR_SELECT, FOLDER_SELECT, SEARCH_NOW = range(6)


def _radarr(context: ContextTypes.DEFAULT_TYPE) -> RadarrClient:
    return RadarrClient(context.application.bot_data["config"])


def _authorized(user_id: int, config: dict) -> bool:
    return acl_store.is_authorized(user_id) or user_id == config["OWNER_ID"]


async def query_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    config = context.application.bot_data["config"]
    if not _authorized(update.effective_user.id, config):
        await update.message.reply_text("Unauthorized. Use /auth <password> to get access.")
        return ConversationHandler.END

    if not context.args:
        await update.message.reply_text("Usage: /query <movie title>")
        return ConversationHandler.END

    query = " ".join(context.args)

    try:
        results = await _radarr(context).search_movies(query)
    except RadarrError as e:
        logger.error("Radarr search failed: %s", e)
        await update.message.reply_text(f"Radarr search failed: {e}")
        return ConversationHandler.END

    if not results:
        await update.message.reply_text("No results found.")
        return ConversationHandler.END

    max_results = config.get("MAX_RESULTS", 15)
    results = results[:max_results]
    context.user_data["movie_results"] = results

    lines = [f"{i+1}. {m.get('title', '?')} ({m.get('year', '?')})" for i, m in enumerate(results)]
    await update.message.reply_text(
        "Search results:\n\n" + "\n".join(lines) + "\n\nReply with a number to select, or /clear to cancel."
    )
    return MOVIE_SELECT


async def movie_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    results = context.user_data.get("movie_results", [])
    try:
        idx = int(update.message.text.strip()) - 1
        assert 0 <= idx < len(results)
    except (ValueError, AssertionError):
        await update.message.reply_text(f"Enter a number between 1 and {len(results)}.")
        return MOVIE_SELECT

    movie = results[idx]
    context.user_data["selected_movie"] = movie

    overview = movie.get("overview") or "No description available."
    if len(overview) > 300:
        overview = overview[:297] + "..."

    await update.message.reply_text(
        f"{movie.get('title', '?')} ({movie.get('year', '?')})\n\n"
        f"{overview}\n\n"
        "Add this movie? Reply yes or no."
    )
    return CONFIRM


async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip().lower()
    if text not in ("yes", "y", "no", "n"):
        await update.message.reply_text("Reply yes or no.")
        return CONFIRM

    if text in ("no", "n"):
        context.user_data.clear()
        await update.message.reply_text("Cancelled.")
        return ConversationHandler.END

    try:
        profiles = await _radarr(context).get_quality_profiles()
    except RadarrError as e:
        logger.error("Failed to get quality profiles: %s", e)
        await update.message.reply_text(f"Failed to get quality profiles: {e}")
        return ConversationHandler.END

    if not profiles:
        await update.message.reply_text("No quality profiles found in Radarr.")
        return ConversationHandler.END

    context.user_data["profiles"] = profiles
    lines = [f"{i+1}. {p['name']}" for i, p in enumerate(profiles)]
    await update.message.reply_text("Select a quality profile:\n\n" + "\n".join(lines))
    return PROFILE_SELECT


async def profile_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    profiles = context.user_data.get("profiles", [])
    try:
        idx = int(update.message.text.strip()) - 1
        assert 0 <= idx < len(profiles)
    except (ValueError, AssertionError):
        await update.message.reply_text(f"Enter a number between 1 and {len(profiles)}.")
        return PROFILE_SELECT

    context.user_data["selected_profile"] = profiles[idx]
    await update.message.reply_text(
        "Monitor this movie?\n\n1. Yes — monitor for new releases\n2. No — add unmonitored"
    )
    return MONITOR_SELECT


async def monitor_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if text == "1":
        context.user_data["monitored"] = True
    elif text == "2":
        context.user_data["monitored"] = False
    else:
        await update.message.reply_text("Reply 1 or 2.")
        return MONITOR_SELECT

    try:
        folders = await _radarr(context).get_root_folders()
    except RadarrError as e:
        logger.error("Failed to get root folders: %s", e)
        await update.message.reply_text(f"Failed to get root folders: {e}")
        return ConversationHandler.END

    if not folders:
        await update.message.reply_text("No root folders found in Radarr.")
        return ConversationHandler.END

    context.user_data["folders"] = folders
    lines = [f"{i+1}. {f['path']}" for i, f in enumerate(folders)]
    await update.message.reply_text("Select a root folder:\n\n" + "\n".join(lines))
    return FOLDER_SELECT


async def folder_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    folders = context.user_data.get("folders", [])
    try:
        idx = int(update.message.text.strip()) - 1
        assert 0 <= idx < len(folders)
    except (ValueError, AssertionError):
        await update.message.reply_text(f"Enter a number between 1 and {len(folders)}.")
        return FOLDER_SELECT

    context.user_data["selected_folder"] = folders[idx]["path"]
    await update.message.reply_text(
        "Search for this movie immediately?\n\n1. Yes\n2. No — add to library and wait for RSS"
    )
    return SEARCH_NOW


async def search_now(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if text == "1":
        search = True
    elif text == "2":
        search = False
    else:
        await update.message.reply_text("Reply 1 or 2.")
        return SEARCH_NOW

    movie = context.user_data["selected_movie"]
    profile = context.user_data["selected_profile"]
    folder = context.user_data["selected_folder"]
    monitored = context.user_data["monitored"]

    try:
        await _radarr(context).add_movie(
            movie=movie,
            quality_profile_id=profile["id"],
            root_folder=folder,
            monitored=monitored,
            search_now=search,
        )
    except RadarrError as e:
        logger.error("Failed to add movie: %s", e)
        if e.status_code == 400:
            await update.message.reply_text("This movie is already in your library.")
        else:
            await update.message.reply_text(f"Failed to add movie: {e}")
        context.user_data.clear()
        return ConversationHandler.END

    title = movie.get("title", "?")
    year = movie.get("year", "?")
    status = "queued for download" if search else "added to library (waiting for RSS)"
    await update.message.reply_text(f"{title} ({year}) {status}.")
    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text("Cancelled.")
    return ConversationHandler.END


def query_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("query", query_start)],
        states={
            MOVIE_SELECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, movie_select)],
            CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm)],
            PROFILE_SELECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, profile_select)],
            MONITOR_SELECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, monitor_select)],
            FOLDER_SELECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, folder_select)],
            SEARCH_NOW: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_now)],
        },
        fallbacks=[CommandHandler("clear", cancel), CommandHandler("cancel", cancel)],
        per_user=True,
    )
