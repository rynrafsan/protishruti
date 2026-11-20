"""Admin sign-in for /docs.

Two roles, each with its own password from the environment (never stored in the repo):
  DOCS_ADMIN_PASSWORD       Admin: edit, save drafts, publish, change visibility and the schedule
  DOCS_SUPERADMIN_PASSWORD  Super Admin: everything above + restore old versions, reset content and
                            settings, read the audit log
A password shorter than 12 characters is ignored, so a weak setting cannot open the panel.
The session is an HMAC-signed, HttpOnly, SameSite=Strict cookie that expires after 8 hours.
Every change also needs the X-Docs-Admin header, which a cross-site form cannot send (CSRF).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

COOKIE = "pdocs_session"
SESSION_S = 8 * 3600
MIN_LEN = 12
CSRF_HEADER = "x-docs-admin"
_SECRET = (os.getenv("DOCS_SECRET") or secrets.token_hex(32)).encode()  # random: sessions end on restart

_fails: dict[str, deque] = defaultdict(deque)
_all_fails: deque = deque()
_lock = threading.Lock()
WINDOW_S, PER_IP, GLOBAL = 15 * 60, 5, 40


def _pw(name: str) -> str:
    v = os.getenv(name, "")
    return v if len(v) >= MIN_LEN else ""


def roles_enabled() -> dict:
    return {"admin": bool(_pw("DOCS_ADMIN_PASSWORD")), "super": bool(_pw("DOCS_SUPERADMIN_PASSWORD"))}


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _sign(payload: str) -> str:
    return _b64(hmac.new(_SECRET, payload.encode(), hashlib.sha256).digest())


def make_token(role: str, name: str) -> str:
    payload = _b64(json.dumps({"r": role, "n": name, "e": int(time.time()) + SESSION_S,
                               "i": secrets.token_hex(4)}).encode())
    return f"{payload}.{_sign(payload)}"


def read_token(token: str | None) -> dict | None:
    if not token or "." not in token:
        return None
    payload, sig = token.rsplit(".", 1)
    if not hmac.compare_digest(sig, _sign(payload)):
        return None
    try:
        data = json.loads(_unb64(payload))
    except ValueError:
        return None
    if data.get("e", 0) < time.time() or data.get("r") not in ("admin", "super"):
        return None
    if not roles_enabled()["super" if data["r"] == "super" else "admin"]:
        return None  # the password was removed: old sessions stop working
    return {"role": data["r"], "name": data.get("n") or "Admin"}


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    return (fwd.split(",")[0].strip() if fwd else "") or (request.client.host if request.client else "?")


def check_password(password: str, ip: str) -> str | None:
    """Returns the role, or None. Raises 429 after too many failures."""
    now = time.time()
    with _lock:
        for q in (_fails[ip], _all_fails):
            while q and q[0] < now - WINDOW_S:
                q.popleft()
        if len(_fails[ip]) >= PER_IP or len(_all_fails) >= GLOBAL:
            raise HTTPException(429, "Too many wrong passwords. Try again in 15 minutes.")
    role = None
    given = (password or "").encode()
    for r, env in (("super", "DOCS_SUPERADMIN_PASSWORD"), ("admin", "DOCS_ADMIN_PASSWORD")):
        pw = _pw(env)
        if pw and hmac.compare_digest(given, pw.encode()):
            role = r
            break
    if role is None:
        with _lock:
            _fails[ip].append(now)
            _all_fails.append(now)
    return role


def current(request: Request) -> dict | None:
    return read_token(request.cookies.get(COOKIE))


def is_https(request: Request) -> bool:
    return request.url.scheme == "https" or request.headers.get("x-forwarded-proto", "") == "https"


def require(request: Request, role: str = "admin") -> dict:
    who = current(request)
    if not who:
        raise HTTPException(401, "Sign in as an admin first.")
    if role == "super" and who["role"] != "super":
        raise HTTPException(403, "Only a Super Admin can do this.")
    if request.method not in ("GET", "HEAD") and request.headers.get(CSRF_HEADER) != "1":
        raise HTTPException(403, "Missing the X-Docs-Admin header.")
    return who
