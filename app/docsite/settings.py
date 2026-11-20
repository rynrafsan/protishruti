"""Who can see /docs, and when.

Defaults come from environment variables, so they survive restarts on hosts without a disk
(Render's free plan). Changes made in the admin panel are saved to DOCS_DATA_DIR/settings.json
and win over the defaults until a Super Admin resets them.
"""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .. import config

BD = timezone(timedelta(hours=6))  # the competition and the users run on Bangladesh time
DATA_DIR = Path(os.getenv("DOCS_DATA_DIR", str(config.ROOT / "data" / "runtime" / "docs")))
FILE = DATA_DIR / "settings.json"                          # changes made in the admin panel (this server)
COMMITTED = config.ROOT / "data" / "docs" / "settings.json"  # committed by the GitHub sync (survives restarts)
_lock = threading.Lock()

CLOSED_MESSAGE = "The Protishruti documentation is open only during the judging window."


def _env(name: str, default: str) -> str:
    return (os.getenv(name) or default).split("#")[0].strip()


def parse_time(value) -> datetime | None:
    """ISO 8601 with or without an offset; a time without an offset is Bangladesh time."""
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=BD)


def iso(dt: datetime | None) -> str | None:
    return dt.astimezone(BD).isoformat(timespec="minutes") if dt else None


def defaults() -> dict:
    return {
        "enabled": _env("DOCS_PUBLIC", "true").lower() == "true",
        "schedule": _env("DOCS_SCHEDULE", "true").lower() == "true",
        # Judging period of the International AI Builders Congress 2026 (preliminary -> final round)
        "start": iso(parse_time(_env("DOCS_OPEN_FROM", "2026-11-20T00:00"))),
        "end": iso(parse_time(_env("DOCS_OPEN_UNTIL", "2026-12-31T23:59"))),
        "closed_message": _env("DOCS_CLOSED_MESSAGE", CLOSED_MESSAGE),
        "updated_at": None,
        "updated_by": "environment defaults",
        "source": "environment",
    }


def load() -> dict:
    """Environment defaults, then the committed file, then this server's admin changes."""
    base = defaults()
    for path, label in ((COMMITTED, "repository (data/docs/settings.json)"), (FILE, "admin panel")):
        if path.exists():
            try:
                saved = json.loads(path.read_text(encoding="utf-8"))
                base.update({k: saved[k] for k in base if k in saved and k != "source"})
                base["source"] = label
            except (ValueError, OSError):
                pass
    return base


def public_fields(s: dict) -> dict:
    return {k: s[k] for k in ("enabled", "schedule", "start", "end", "closed_message", "updated_at", "updated_by")}


def save(changes: dict, by: str) -> dict:
    """Validate and store an admin change. Raises ValueError with a readable reason."""
    cur = load()
    new = dict(cur)
    if "duration_hours" in changes and changes["duration_hours"] not in (None, ""):
        hours = float(changes["duration_hours"])
        if not 0 < hours <= 24 * 366:
            raise ValueError("Duration must be between 1 minute and one year.")
        now = datetime.now(BD).replace(second=0, microsecond=0)
        new.update(enabled=True, schedule=True, start=iso(now), end=iso(now + timedelta(hours=hours)))
    else:
        for key in ("enabled", "schedule"):
            if key in changes:
                new[key] = bool(changes[key])
        for key in ("start", "end"):
            if key in changes:
                try:
                    new[key] = iso(parse_time(changes[key]))
                except ValueError:
                    raise ValueError(f"'{changes[key]}' is not a date and time.")
    if "closed_message" in changes:
        new["closed_message"] = (str(changes["closed_message"] or "").strip() or CLOSED_MESSAGE)[:300]
    s, e = parse_time(new["start"]), parse_time(new["end"])
    if s and e and e <= s:
        raise ValueError("The end must be after the start.")
    new.update(updated_at=iso(datetime.now(BD)), updated_by=by[:60], source="admin panel")
    with _lock:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        tmp = FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(new, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, FILE)
    return new


def reset() -> dict:
    with _lock:
        FILE.unlink(missing_ok=True)
    return load()


def status(now: datetime | None = None, s: dict | None = None) -> dict:
    """Is /docs open to the public right now, and why (not)."""
    s = s or load()
    now = now or datetime.now(BD)
    start, end = parse_time(s["start"]), parse_time(s["end"])
    if not s["enabled"]:
        state = "off"
    elif s["schedule"] and start and now < start:
        state = "scheduled"
    elif s["schedule"] and end and now >= end + timedelta(minutes=1):  # the end minute itself is included
        state = "ended"
    else:
        state = "open"
    return {"open": state == "open", "state": state, "now": iso(now),
            "start": iso(start) if s["schedule"] else None, "end": iso(end) if s["schedule"] else None,
            "closed_message": s["closed_message"]}
