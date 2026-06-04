import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def load_config() -> dict:
    path = os.path.join(BASE_DIR, "env.json")
    try:
        with open(path) as f:
            cfg = json.load(f)
    except FileNotFoundError:
        print("ERROR: env.json not found. Copy env.json.example and fill in the values.")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"ERROR: env.json is malformed: {e}")
        sys.exit(1)

    required = ["TELEGRAM_BOT_TOKEN", "BOT_PASSWORD", "OWNER_ID", "RADARR_HOST", "RADARR_API_KEY"]
    missing = [k for k in required if not cfg.get(k)]
    if missing:
        print(f"ERROR: Missing required config keys: {', '.join(missing)}")
        sys.exit(1)

    cfg.setdefault("MAX_RESULTS", 15)
    cfg.setdefault("RADARR_PORT", 7878)
    cfg.setdefault("RADARR_SSL", False)
    cfg.setdefault("RADARR_VERIFY_SSL", True)
    cfg.setdefault("RADARR_URL_BASE", "")

    # Telegram user IDs and ports are compared against ints elsewhere, so coerce
    # them here. JSON lets users quote these by accident, which would silently
    # lock the owner out of every admin command (str != int).
    for key in ("OWNER_ID", "MAX_RESULTS", "RADARR_PORT"):
        try:
            cfg[key] = int(cfg[key])
        except (TypeError, ValueError):
            print(f"ERROR: config key {key} must be an integer, got: {cfg[key]!r}")
            sys.exit(1)

    return cfg
