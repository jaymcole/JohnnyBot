import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ACL_PATH = os.path.join(BASE_DIR, "acl.json")

_EMPTY: dict = {"allowedUsers": [], "revokedUsers": []}


def _load() -> dict:
    try:
        with open(ACL_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return dict(_EMPTY)


def _save(acl: dict) -> None:
    with open(ACL_PATH, "w") as f:
        json.dump(acl, f, indent=2)


def is_authorized(user_id: int) -> bool:
    acl = _load()
    return user_id in acl["allowedUsers"] and user_id not in acl["revokedUsers"]


def is_revoked(user_id: int) -> bool:
    return user_id in _load()["revokedUsers"]


def add_user(user_id: int) -> None:
    acl = _load()
    if user_id not in acl["allowedUsers"]:
        acl["allowedUsers"].append(user_id)
    if user_id in acl["revokedUsers"]:
        acl["revokedUsers"].remove(user_id)
    _save(acl)


def revoke_user(user_id: int) -> None:
    acl = _load()
    if user_id not in acl["revokedUsers"]:
        acl["revokedUsers"].append(user_id)
    _save(acl)


def unrevoke_user(user_id: int) -> None:
    acl = _load()
    if user_id in acl["revokedUsers"]:
        acl["revokedUsers"].remove(user_id)
    _save(acl)


def get_active_users() -> list[int]:
    acl = _load()
    return [u for u in acl["allowedUsers"] if u not in acl["revokedUsers"]]


def get_revoked_users() -> list[int]:
    return _load()["revokedUsers"]
