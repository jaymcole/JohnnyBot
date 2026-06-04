"""Discord bot for remotely managing a Telegram bot running on the same server.

Exposes two guild-scoped slash commands:
  /restart-telegram  - kill and relaunch the Telegram bot process
  /update-self       - pull the latest code and restart via the watchdog
"""

import json
import os
import signal
import subprocess
import time

import discord
from discord import app_commands

# --- Configuration -----------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def load_json(filename):
    with open(os.path.join(BASE_DIR, filename)) as f:
        return json.load(f)


# All configuration (secrets and settings) lives in env.json, which is
# gitignored. Copy env.json.example to env.json and fill in the values.
env = load_json("env.json")

DISCORD_TOKEN = env["DISCORD_TOKEN"]
DISCORD_GUILD_ID = int(env["DISCORD_GUILD_ID"])
ALLOWED_USER_IDS = [int(uid) for uid in env["ALLOWED_USER_IDS"]]
TELEGRAM_BOT_DIR = env["TELEGRAM_BOT_DIR"]
TELEGRAM_BOT_COMMAND = env["TELEGRAM_BOT_COMMAND"]
TELEGRAM_PID_FILE = env["TELEGRAM_PID_FILE"]

GUILD = discord.Object(id=DISCORD_GUILD_ID)

# --- Bot initialisation ------------------------------------------------------

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)


@client.event
async def on_ready():
    # Guild sync is instant; global sync can take up to an hour.
    tree.copy_global_to(guild=GUILD)
    await tree.sync(guild=GUILD)
    print(f"Logged in as {client.user} (ID: {client.user.id})")


# --- Security helper ---------------------------------------------------------

def is_authorised(interaction: discord.Interaction) -> bool:
    """Return True only for allowlisted users acting within the configured guild."""
    return (
        interaction.guild_id == DISCORD_GUILD_ID
        and interaction.user.id in ALLOWED_USER_IDS
    )


# --- Commands ----------------------------------------------------------------

@tree.command(
    name="restart-telegram",
    description="Kill and relaunch the Telegram bot process.",
    guild=GUILD,
)
async def restart_telegram(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    if not is_authorised(interaction):
        await interaction.followup.send("Unauthorised", ephemeral=True)
        return

    # Attempt to kill the existing process, if any.
    if os.path.exists(TELEGRAM_PID_FILE):
        try:
            with open(TELEGRAM_PID_FILE) as f:
                old_pid = int(f.read().strip())
            try:
                os.kill(old_pid, signal.SIGTERM)
            except ProcessLookupError:
                # Process already dead — that's fine, continue.
                pass
            except PermissionError:
                await interaction.followup.send(
                    f"❌ Permission denied killing process {old_pid}. Aborting.",
                    ephemeral=True,
                )
                return
            os.remove(TELEGRAM_PID_FILE)
        except (ValueError, OSError) as e:
            await interaction.followup.send(
                f"⚠️ Could not process existing PID file: {e}. Continuing.",
                ephemeral=True,
            )

    # Give the old process a moment to shut down cleanly.
    time.sleep(1)

    # Launch the Telegram bot as a detached background subprocess.
    try:
        process = subprocess.Popen(
            TELEGRAM_BOT_COMMAND.split(),
            cwd=TELEGRAM_BOT_DIR,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,  # Detaches from the Discord bot's process group.
        )
    except Exception as e:
        await interaction.followup.send(
            f"❌ Failed to launch Telegram bot: {e}",
            ephemeral=True,
        )
        return

    # Record the new PID so it survives Discord bot restarts.
    with open(TELEGRAM_PID_FILE, "w") as f:
        f.write(str(process.pid))

    await interaction.followup.send(
        f"✅ Telegram bot restarted (PID: {process.pid}).",
        ephemeral=True,
    )


@tree.command(
    name="update-self",
    description="Pull the latest code and restart the Discord bot.",
    guild=GUILD,
)
async def update_self(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    if not is_authorised(interaction):
        await interaction.followup.send("Unauthorised", ephemeral=True)
        return

    # Pull the latest code.
    pull = subprocess.run(
        ["git", "pull", "origin", "main"],
        capture_output=True,
        text=True,
    )
    if pull.returncode != 0:
        await interaction.followup.send(
            f"❌ git pull failed:\n```\n{pull.stderr or pull.stdout}\n```",
            ephemeral=True,
        )
        return

    # Syntax-check the new code before exiting, so a bad push can't take the
    # bot permanently offline.
    result = subprocess.run(
        ["python3", "-m", "py_compile", "bot.py"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        await interaction.followup.send(
            f"❌ Syntax check failed, not restarting:\n```\n{result.stderr}\n```",
            ephemeral=True,
        )
        return

    await interaction.followup.send(
        "✅ Update successful, restarting…",
        ephemeral=True,
    )

    # Exit cleanly — the watchdog (run_bot.sh) handles the restart.
    await client.close()


# --- Entry point -------------------------------------------------------------

if __name__ == "__main__":
    client.run(DISCORD_TOKEN)
