#!/bin/bash

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cd "$REPO_DIR"

while true; do
    echo "[watchdog] Starting bot at $(date)"
    python3 bot.py
    EXIT_CODE=$?
    echo "[watchdog] Bot exited with code $EXIT_CODE at $(date)"

    echo "[watchdog] Pulling latest code..."
    git pull origin main

    echo "[watchdog] Restarting in 2 seconds..."
    sleep 2
done
