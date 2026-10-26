"""
Job Board Sign-in
=================
Each app user gets their own browser profile (browser_profile/user_<id>/) that the
Auto-Apply Agent reuses. Before the agent applies on a job board for the first time,
the user signs in to that board once, by hand, in a visible browser window opened
with that profile. The agent itself never logs in.

Sign-in state is kept in browser_profile/user_<id>/job_boards.json:
    {"linkedin": {"signed_in": true, "verified": true, "updated_at": "..."}}

"verified" is true when the session cookie was seen in the browser (LinkedIn's li_at).
For boards whose session cookie we don't check, the user confirms the sign-in instead.
"""

import os
import json
import time
import threading
from datetime import datetime, timezone
from urllib.parse import urlparse

PROFILE_ROOT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "browser_profile")
STATE_FILE = "job_boards.json"
LOGIN_WINDOW_TIMEOUT_S = 15 * 60  # close an abandoned sign-in window after 15 minutes

# auth_cookie: the cookie that only exists while signed in. None = can't verify, ask the user.
BOARDS = {
    "linkedin": {
        "name": "LinkedIn",
        "hosts": ("linkedin.com",),
        "login_url": "https://www.linkedin.com/login",
        "cookie_url": "https://www.linkedin.com",
        "auth_cookie": "li_at",
    },
    "indeed": {
        "name": "Indeed",
        "hosts": ("indeed.com",),
        "login_url": "https://secure.indeed.com/auth",
        "cookie_url": None,
        "auth_cookie": None,
    },
    "jobsdb": {
        "name": "JobsDB",
        "hosts": ("jobsdb.com",),
        "login_url": "https://th.jobsdb.com/th",  # sign in from the site's own header
        "cookie_url": None,
        "auth_cookie": None,
    },
    "jobbkk": {
        "name": "JobBKK",
        "hosts": ("jobbkk.com",),
        "login_url": "https://www.jobbkk.com/",  # sign in from the site's own header
        "cookie_url": None,
        "auth_cookie": None,
    },
}

BROWSER_ARGS = dict(
    headless=False,
    viewport={"width": 1280, "height": 900},
    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
)

# Chromium locks a profile folder, so one window per user at a time (sign-in or auto-apply).
_locks: dict = {}
_locks_guard = threading.Lock()


def profile_lock(user_key: str) -> threading.Lock:
    with _locks_guard:
        return _locks.setdefault(user_key, threading.Lock())


def profile_dir(user_key: str) -> str:
    """user_key is the agent's user id string, e.g. "user_3"."""
    path = os.path.join(PROFILE_ROOT, user_key)
    os.makedirs(path, exist_ok=True)
    return path


def board_for_url(url: str):
    """Returns the board key for a job link, or None for sites that need no sign-in."""
    host = (urlparse(url or "").hostname or "").lower()
    for key, board in BOARDS.items():
        if any(host == h or host.endswith("." + h) for h in board["hosts"]):
            return key
    return None


def _state_path(user_key: str) -> str:
    return os.path.join(profile_dir(user_key), STATE_FILE)


def load_state(user_key: str) -> dict:
    try:
        with open(_state_path(user_key), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def set_signed_in(user_key: str, board: str, signed_in: bool, verified: bool = False) -> dict:
    state = load_state(user_key)
    state[board] = {
        "signed_in": bool(signed_in),
        "verified": bool(verified),
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    with open(_state_path(user_key), "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    return state[board]


def status(user_key: str) -> list:
    """Sign-in status of every board, for the UI."""
    state = load_state(user_key)
    out = []
    for key, board in BOARDS.items():
        s = state.get(key, {})
        out.append({
            "key": key,
            "name": board["name"],
            "hosts": list(board["hosts"]),
            "signed_in": bool(s.get("signed_in")),
            "verified": bool(s.get("verified")),
            "updated_at": s.get("updated_at"),
            "can_verify": board["auth_cookie"] is not None,
        })
    return out


def missing_sign_ins(user_key: str, job_links: list) -> list:
    """Boards the given jobs are on that this user hasn't signed in to yet."""
    state = load_state(user_key)
    needed = []
    for link in job_links:
        key = board_for_url(link)
        if key and key not in needed and not state.get(key, {}).get("signed_in"):
            needed.append(key)
    return needed


def _has_auth_cookie(context, board: dict) -> bool:
    cookies = context.cookies([board["cookie_url"]])
    return any(c["name"] == board["auth_cookie"] and c.get("value") for c in cookies)


def open_sign_in_window(user_key: str, board_key: str) -> dict:
    """
    Opens a visible browser on the user's own profile at the board's sign-in page and
    blocks until the user closes it (or, for verifiable boards, until the sign-in is seen).

    Returns {"board", "signed_in": True | False | None}; None means "can't tell, ask the user".
    """
    from playwright.sync_api import sync_playwright

    board = BOARDS[board_key]
    lock = profile_lock(user_key)
    if not lock.acquire(blocking=False):
        raise RuntimeError("A browser window for your account is already open. Finish there first.")
    try:
        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(user_data_dir=profile_dir(user_key), **BROWSER_ARGS)
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(board["login_url"], wait_until="domcontentloaded")

            signed_in = None if board["auth_cookie"] is None else False
            deadline = time.monotonic() + LOGIN_WINDOW_TIMEOUT_S
            seen_at = None
            while time.monotonic() < deadline:
                try:
                    if not context.pages:
                        break
                    if board["auth_cookie"] is not None and _has_auth_cookie(context, board):
                        signed_in = True
                        # Give the site a moment to finish its redirects, then close for the user.
                        seen_at = seen_at or time.monotonic()
                        if time.monotonic() - seen_at > 3:
                            break
                    context.pages[-1].wait_for_timeout(1000)
                except Exception:
                    break  # the user closed the window
            try:
                context.close()
            except Exception:
                pass
    finally:
        lock.release()

    if signed_in is not None:
        set_signed_in(user_key, board_key, signed_in, verified=True)
    return {"board": board_key, "signed_in": signed_in}


if __name__ == "__main__":
    # Manual use: python tools/job_boards.py user_1 linkedin
    import sys
    if len(sys.argv) != 3 or sys.argv[2] not in BOARDS:
        print(f"Usage: python tools/job_boards.py <user_key, e.g. user_1> <{'|'.join(BOARDS)}>")
        sys.exit(1)
    result = open_sign_in_window(sys.argv[1], sys.argv[2])
    if result["signed_in"] is None:
        set_signed_in(sys.argv[1], sys.argv[2], True)
        result["signed_in"] = True
    print(result)
