"""JohnnyBot — Telegram bot for Radarr movie management."""

import logging
import sys

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

import acl as acl_store
from config import load_config
from handlers.admin import (
    cid_command,
    refresh_command,
    revoke_conversation,
    rss_command,
    unrevoke_conversation,
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
    "/clear — Cancel current operation\n\n"
    "Admin only:\n"
    "/rss — Trigger RSS sync\n"
    "/wanted — Search for wanted movies\n"
    "/refresh — Refresh library\n"
    "/cid — Show chat ID\n"
    "/users — List authorized users\n"
    "/revoke — Revoke a user\n"
    "/unrevoke — Restore a user"
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

    if acl_store.is_authorized(user_id) or user_id == config["OWNER_ID"]:
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


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.clear()
    await update.message.reply_text("Cleared.")


def main() -> None:
    config = load_config()

    app = Application.builder().token(config["TELEGRAM_BOT_TOKEN"]).build()
    app.bot_data["config"] = config

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("auth", auth_command))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(query_conversation())
    app.add_handler(CommandHandler("library", library_command))
    app.add_handler(CommandHandler("upcoming", upcoming_command))
    app.add_handler(CommandHandler("rss", rss_command))
    app.add_handler(CommandHandler("wanted", wanted_command))
    app.add_handler(CommandHandler("refresh", refresh_command))
    app.add_handler(CommandHandler("cid", cid_command))
    app.add_handler(CommandHandler("users", users_command))
    app.add_handler(revoke_conversation())
    app.add_handler(unrevoke_conversation())

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
