"""JohnnyBot — Telegram bot for Radarr movie management."""

import logging
import os
import sys

from telegram import Update
from telegram.error import TelegramError
from telegram.ext import Application, CommandHandler, ContextTypes

import acl as acl_store
from config import load_config
import discord_log

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
from handlers.admin import (
    cid_command,
    refresh_command,
    restart_command,
    revoke_conversation,
    rss_command,
    unrevoke_conversation,
    update_command,
    users_command,
    wanted_command,
)
from handlers.library import library_command, upcoming_command
from handlers.movies import query_conversation

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[logging.StreamHandler(sys.stdout)],
)
logging.getLogger("httpx").setLevel(logging.WARNING)

HELP_TEXT = (
    "Available commands:\n\n"
    "/query <title> — Search and add a movie\n"
    "/library [query] — Search your library\n"
    "/upcoming [days] — Upcoming releases (default: 30)\n"
    "/auth <password> — Authenticate with the bot\n"
    "/myid — Show your Telegram user ID\n"
    "/clear — Cancel current operation\n\n"
    "Admin only:\n"
    "/rss — Trigger RSS sync\n"
    "/wanted — Search for wanted movies\n"
    "/refresh — Refresh library\n"
    "/cid — Show chat ID\n"
    "/users — List authorized users\n"
    "/revoke — Revoke a user\n"
    "/unrevoke — Restore a user\n"
    "/restart — Restart the bot\n"
    "/update — Pull latest code and restart"
)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Welcome to JohnnyBot.\n\n"
        "Use /auth <password> to get started, or /help to see all commands."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP_TEXT)


async def auth_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    config = context.application.bot_data["config"]

    if acl_store.is_revoked(user_id):
        await update.message.reply_text("Your access has been revoked.")
        return

    if acl_store.is_authorized(user_id) or user_id in config["OWNER_IDS"]:
        await update.message.reply_text("You are already authorized.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /auth <password>")
        return

    if context.args[0] == config["BOT_PASSWORD"]:
        acl_store.add_user(user_id)
        await update.message.reply_text("Access granted. Use /help to see available commands.")
    else:
        await update.message.reply_text("Incorrect password.")


async def myid_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(f"Your Telegram user ID is: {update.effective_user.id}")


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.clear()
    await update.message.reply_text("Nothing in progress.")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Catch anything a handler missed so the user gets feedback instead of silence."""
    logger = logging.getLogger(__name__)

    # Build a rich context string so the Discord log tells us exactly what
    # triggered the error without needing to correlate other log lines.
    parts = []
    if isinstance(update, Update):
        if update.effective_user:
            u = update.effective_user
            parts.append(f"user={u.id} ({u.username or u.first_name})")
        if update.effective_chat:
            parts.append(f"chat={update.effective_chat.id}")
        if update.effective_message and update.effective_message.text:
            parts.append(f"text={update.effective_message.text[:80]!r}")

    ctx = " | ".join(parts) if parts else "no update context"
    logger.error("Unhandled exception [%s]", ctx, exc_info=context.error)

    if isinstance(update, Update) and update.effective_message:
        config = context.application.bot_data.get("config", {})
        is_owner = (
            update.effective_user is not None
            and update.effective_user.id in config.get("OWNER_IDS", [])
        )
        if is_owner:
            err_type = type(context.error).__name__
            reply = f"Error ({err_type}): {context.error}"
        else:
            reply = "Something went wrong. Please try again."
        try:
            await update.effective_message.reply_text(reply)
        except TelegramError:
            pass


def main() -> None:
    config = load_config()

    webhook_url = config.get("DISCORD_WEBHOOK_URL", "")
    if webhook_url:
        logging.getLogger().addHandler(discord_log.DiscordWebhookHandler(webhook_url))

    app = Application.builder().token(config["TELEGRAM_BOT_TOKEN"]).build()
    app.bot_data["config"] = config

    # Conversation handlers must be registered before the bare /clear command so
    # that, while a conversation is active, the conversation's own /clear fallback
    # wins and actually ends it. Otherwise the top-level /clear consumes the
    # update, wipes user_data, and leaves the conversation stuck mid-flow.
    app.add_handler(query_conversation())
    app.add_handler(revoke_conversation())
    app.add_handler(unrevoke_conversation())

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("myid", myid_command))
    app.add_handler(CommandHandler("auth", auth_command))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(CommandHandler("library", library_command))
    app.add_handler(CommandHandler("upcoming", upcoming_command))
    app.add_handler(CommandHandler("rss", rss_command))
    app.add_handler(CommandHandler("wanted", wanted_command))
    app.add_handler(CommandHandler("refresh", refresh_command))
    app.add_handler(CommandHandler("cid", cid_command))
    app.add_handler(CommandHandler("users", users_command))
    app.add_handler(CommandHandler("restart", restart_command))
    app.add_handler(CommandHandler("update", update_command))

    app.add_error_handler(error_handler)

    try:
        import subprocess
        commit = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=REPO_DIR, text=True
        ).strip()
    except Exception:
        commit = "unknown"
    discord_log.send(webhook_url, f"🟢 JohnnyBot started (commit `{commit}`)")
    try:
        app.run_polling(drop_pending_updates=True)
    finally:
        discord_log.send(webhook_url, "🔴 JohnnyBot stopped — watchdog will restart")


if __name__ == "__main__":
    main()
