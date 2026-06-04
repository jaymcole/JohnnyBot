import asyncio
import logging
import os
import signal
import sys

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

REVOKE_SELECT, REVOKE_CONFIRM = 0, 1
UNREVOKE_SELECT, UNREVOKE_CONFIRM = 0, 1

# Repo root is one level above this file (handlers/).
REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# SIGTERM is the clean shutdown signal on Linux. Windows only supports SIGINT
# via os.kill, which python-telegram-bot handles identically.
_SHUTDOWN_SIGNAL = signal.SIGINT if sys.platform == "win32" else signal.SIGTERM


def _radarr(context: ContextTypes.DEFAULT_TYPE) -> RadarrClient:
    return RadarrClient(context.application.bot_data["config"])


def _is_admin(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    return user_id in context.application.bot_data["config"]["OWNER_IDS"]


async def rss_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update.effective_user.id, context):
        await update.message.reply_text("Admin only.")
        return
    try:
        await _radarr(context).rss_sync()
        await update.message.reply_text("RSS sync triggered.")
    except RadarrError as e:
        await update.message.reply_text(f"RSS sync failed: {e}")


async def wanted_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update.effective_user.id, context):
        await update.message.reply_text("Admin only.")
        return
    try:
        await _radarr(context).wanted_search()
        await update.message.reply_text("Wanted search triggered.")
    except RadarrError as e:
        await update.message.reply_text(f"Wanted search failed: {e}")


async def refresh_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update.effective_user.id, context):
        await update.message.reply_text("Admin only.")
        return
    try:
        await _radarr(context).refresh_library()
        await update.message.reply_text("Library refresh triggered.")
    except RadarrError as e:
        await update.message.reply_text(f"Library refresh failed: {e}")


async def cid_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update.effective_user.id, context):
        await update.message.reply_text("Admin only.")
        return
    await update.message.reply_text(f"Chat ID: {update.effective_chat.id}")


async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update.effective_user.id, context):
        await update.message.reply_text("Admin only.")
        return

    active = acl_store.get_active_users()
    revoked = acl_store.get_revoked_users()

    lines = []
    if active:
        lines.append("Active users:")
        lines.extend(f"  {uid}" for uid in active)
    if revoked:
        lines.append("Revoked users:")
        lines.extend(f"  {uid}" for uid in revoked)
    if not active and not revoked:
        lines.append("No users registered.")

    await update.message.reply_text("\n".join(lines))


# --- Restart / update ----------------------------------------------------------

async def restart_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update.effective_user.id, context):
        await update.message.reply_text("Admin only.")
        return
    await update.message.reply_text("Restarting...")
    os.kill(os.getpid(), _SHUTDOWN_SIGNAL)


async def update_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update.effective_user.id, context):
        await update.message.reply_text("Admin only.")
        return

    pull = await asyncio.create_subprocess_exec(
        "git", "pull", "origin", "main",
        cwd=REPO_DIR,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await pull.communicate()

    if pull.returncode != 0:
        output = (stderr or stdout).decode().strip()
        await update.message.reply_text(f"git pull failed:\n{output}")
        return

    check = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "py_compile", os.path.join(REPO_DIR, "bot.py"),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, check_err = await check.communicate()

    if check.returncode != 0:
        await update.message.reply_text(
            f"Syntax check failed — not restarting:\n{check_err.decode().strip()}"
        )
        return

    pull_msg = stdout.decode().strip()
    await update.message.reply_text(f"Updated ({pull_msg}), restarting...")
    os.kill(os.getpid(), _SHUTDOWN_SIGNAL)


# --- Revoke conversation -------------------------------------------------------

async def revoke_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not _is_admin(update.effective_user.id, context):
        await update.message.reply_text("Admin only.")
        return ConversationHandler.END

    users = acl_store.get_active_users()
    if not users:
        await update.message.reply_text("No active users to revoke.")
        return ConversationHandler.END

    context.user_data["revoke_candidates"] = users
    lines = [f"{i+1}. {uid}" for i, uid in enumerate(users)]
    await update.message.reply_text(
        "Select user to revoke:\n\n" + "\n".join(lines) + "\n\nOr /clear to cancel."
    )
    return REVOKE_SELECT


async def revoke_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    candidates = context.user_data.get("revoke_candidates", [])
    try:
        idx = int(update.message.text.strip()) - 1
        assert 0 <= idx < len(candidates)
    except (ValueError, AssertionError):
        await update.message.reply_text(f"Enter a number between 1 and {len(candidates)}.")
        return REVOKE_SELECT

    context.user_data["revoke_target"] = candidates[idx]
    await update.message.reply_text(
        f"Revoke access for user {candidates[idx]}? Reply yes or no."
    )
    return REVOKE_CONFIRM


async def revoke_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip().lower()
    if text not in ("yes", "y", "no", "n"):
        await update.message.reply_text("Reply yes or no.")
        return REVOKE_CONFIRM

    target = context.user_data.pop("revoke_target", None)
    context.user_data.pop("revoke_candidates", None)

    if text in ("yes", "y") and target:
        acl_store.revoke_user(target)
        await update.message.reply_text(f"User {target} revoked.")
    else:
        await update.message.reply_text("Cancelled.")

    return ConversationHandler.END


# --- Unrevoke conversation -----------------------------------------------------

async def unrevoke_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not _is_admin(update.effective_user.id, context):
        await update.message.reply_text("Admin only.")
        return ConversationHandler.END

    users = acl_store.get_revoked_users()
    if not users:
        await update.message.reply_text("No revoked users to restore.")
        return ConversationHandler.END

    context.user_data["unrevoke_candidates"] = users
    lines = [f"{i+1}. {uid}" for i, uid in enumerate(users)]
    await update.message.reply_text(
        "Select user to restore:\n\n" + "\n".join(lines) + "\n\nOr /clear to cancel."
    )
    return UNREVOKE_SELECT


async def unrevoke_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    candidates = context.user_data.get("unrevoke_candidates", [])
    try:
        idx = int(update.message.text.strip()) - 1
        assert 0 <= idx < len(candidates)
    except (ValueError, AssertionError):
        await update.message.reply_text(f"Enter a number between 1 and {len(candidates)}.")
        return UNREVOKE_SELECT

    context.user_data["unrevoke_target"] = candidates[idx]
    await update.message.reply_text(
        f"Restore access for user {candidates[idx]}? Reply yes or no."
    )
    return UNREVOKE_CONFIRM


async def unrevoke_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip().lower()
    if text not in ("yes", "y", "no", "n"):
        await update.message.reply_text("Reply yes or no.")
        return UNREVOKE_CONFIRM

    target = context.user_data.pop("unrevoke_target", None)
    context.user_data.pop("unrevoke_candidates", None)

    if text in ("yes", "y") and target:
        acl_store.unrevoke_user(target)
        await update.message.reply_text(f"User {target} restored.")
    else:
        await update.message.reply_text("Cancelled.")

    return ConversationHandler.END


async def _cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text("Cancelled.")
    return ConversationHandler.END


def revoke_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("revoke", revoke_start)],
        states={
            REVOKE_SELECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, revoke_select)],
            REVOKE_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, revoke_confirm)],
        },
        fallbacks=[CommandHandler("clear", _cancel)],
        per_user=True,
    )


def unrevoke_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("unrevoke", unrevoke_start)],
        states={
            UNREVOKE_SELECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, unrevoke_select)],
            UNREVOKE_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, unrevoke_confirm)],
        },
        fallbacks=[CommandHandler("clear", _cancel)],
        per_user=True,
    )
