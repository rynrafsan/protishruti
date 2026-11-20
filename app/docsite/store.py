"""Docs content: the committed default, the published copy, the admin's draft and version history.

data/docs/content.json            committed default (download the current content from the admin
                                  panel and commit it here to make edits permanent)
DOCS_DATA_DIR/published.json      what /docs shows
DOCS_DATA_DIR/draft.json          what the admin is editing
DOCS_DATA_DIR/versions/NNNN.json  every publish, for restore
DOCS_DATA_DIR/audit.jsonl         who changed what, when
On a host without a persistent disk the DOCS_DATA_DIR files reset on restart, and /docs falls back
to the committed default.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import json
import os
import re
import threading
from datetime import datetime
from pathlib import Path

from .. import config
from .sanitize import clean_html, plain, safe_url
from .settings import BD, DATA_DIR

DEFAULT_FILE = config.ROOT / "data" / "docs" / "content.json"
PUBLISHED = DATA_DIR / "published.json"
DRAFT = DATA_DIR / "draft.json"
VERSIONS = DATA_DIR / "versions"
AUDIT = DATA_DIR / "audit.jsonl"
_lock = threading.RLock()

GROUPS = ("pitch", "tech")
TYPES = ("richtext", "team", "diagram", "changelog")
LIVE_KINDS = ("", "summary", "demo", "traction", "features", "stack", "api", "data", "ai", "performance",
              "security", "analytics")
STATUSES = ("upcoming", "planned", "research")
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,40}$")
EMAIL = re.compile(r"^[^@\s<>\"']{1,64}@[^@\s<>\"']{1,190}\.[a-zA-Z]{2,24}$")
PHOTO = re.compile(r"^data:image/(webp|jpeg|png);base64,[A-Za-z0-9+/=]+$")
YOUTUBE = re.compile(r"^https://(www\.)?(youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([A-Za-z0-9_-]{11})")
MAX_BYTES = 3_000_000


class ContentError(ValueError):
    pass


def now() -> str:
    return datetime.now(BD).isoformat(timespec="seconds")


def _read(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def audit(by: str, action: str, detail: str = "") -> None:
    AUDIT.parent.mkdir(parents=True, exist_ok=True)
    with AUDIT.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"at": now(), "by": by, "action": action, "detail": detail[:300]}, ensure_ascii=False) + "\n")


def audit_log(n: int = 100) -> list[dict]:
    if not AUDIT.exists():
        return []
    lines = AUDIT.read_text(encoding="utf-8").splitlines()[-n:]
    return [json.loads(x) for x in reversed(lines) if x.strip()]


# ---------- validation ----------

def _text(v, limit: int) -> str:
    return plain(str(v or ""), limit)


def _figures(items) -> list[dict]:
    out = []
    for f in (items or [])[:4]:
        if not isinstance(f, dict) or not _text(f.get("value"), 24):
            continue
        out.append({"value": _text(f.get("value"), 24), "label": _text(f.get("label"), 140),
                    "source": safe_url(f.get("source")) or ""})
    return out


def clean_section(s: dict) -> dict:
    if not isinstance(s, dict):
        raise ContentError("Each section must be an object.")
    sid = str(s.get("id", "")).strip().lower()
    if not SLUG.match(sid):
        raise ContentError(f"Section id '{sid}' must be lowercase letters, digits and dashes.")
    typ = s.get("type", "richtext")
    if typ not in TYPES:
        raise ContentError(f"Unknown section type '{typ}'.")
    group = s.get("group", "tech")
    if group not in GROUPS:
        raise ContentError(f"Unknown group '{group}'.")
    live = s.get("live") or ""
    if live not in LIVE_KINDS:
        raise ContentError(f"Unknown live panel '{live}'.")
    out = {"id": sid, "group": group, "type": typ, "title": _text(s.get("title"), 120) or sid,
           "kicker": _text(s.get("kicker"), 220), "body": clean_html(s.get("body")),
           "visible": bool(s.get("visible", True)), "live": live, "figures": _figures(s.get("figures"))}
    video = (s.get("video_url") or "").strip()
    if video and not YOUTUBE.match(video):
        raise ContentError("The video link must be a YouTube link (youtube.com/watch?v=… or youtu.be/…).")
    out["video_url"] = video
    if typ == "team":
        members, seen = [], set()
        for m in (s.get("members") or [])[:24]:
            if not isinstance(m, dict) or not _text(m.get("name"), 80):
                continue
            mid = str(m.get("id") or "").strip().lower() or hashlib.sha1(_text(m.get("name"), 80).encode()).hexdigest()[:8]
            if not SLUG.match(mid) or mid in seen:
                mid = hashlib.sha1(f"{mid}{len(seen)}".encode()).hexdigest()[:8]
            seen.add(mid)
            email = _text(m.get("email"), 254)
            if email and not EMAIL.match(email):
                raise ContentError(f"'{email}' is not an email address.")
            photo = m.get("photo") or ""
            if photo and (not PHOTO.match(photo) or len(photo) > 400_000):
                raise ContentError("Team photos must be uploaded through the admin panel.")
            members.append({"id": mid, "name": _text(m.get("name"), 80), "role": _text(m.get("role"), 120),
                            "email": email, "photo": photo, "bio": _text(m.get("bio"), 220)})
        out["team_name"] = _text(s.get("team_name"), 80)
        out["members"] = members
    if typ == "diagram":
        out["mermaid"] = str(s.get("mermaid") or "")[:10_000]
        out["caption"] = _text(s.get("caption"), 300)
    if typ == "changelog":
        out["entries"] = [{"version": _text(e.get("version"), 30), "date": _text(e.get("date"), 30),
                           "notes": clean_html(e.get("notes"), 8000)}
                          for e in (s.get("entries") or [])[:100] if isinstance(e, dict) and _text(e.get("version"), 30)]
    if live == "features":
        out["planned"] = [{"name": _text(p.get("name"), 120), "status": p.get("status") if p.get("status") in STATUSES else "planned",
                           "note": _text(p.get("note"), 300)}
                          for p in (s.get("planned") or [])[:40] if isinstance(p, dict) and _text(p.get("name"), 120)]
    return out


def clean_content(c: dict) -> dict:
    if not isinstance(c, dict) or not isinstance(c.get("sections"), list):
        raise ContentError("Content must have a list of sections.")
    meta = c.get("meta") or {}
    out = {"meta": {"title": _text(meta.get("title"), 120) or "Protishruti",
                    "tagline": _text(meta.get("tagline"), 240),
                    "summary": clean_html(meta.get("summary"), 4000),
                    "app_url": safe_url(meta.get("app_url")) or "/",
                    "repo_url": safe_url(meta.get("repo_url")) or "",
                    "version_label": _text(meta.get("version_label"), 40)},
           "sections": []}
    ids = set()
    for s in c["sections"][:80]:
        sec = clean_section(s)
        if sec["id"] in ids:
            raise ContentError(f"Two sections have the id '{sec['id']}'.")
        ids.add(sec["id"])
        out["sections"].append(sec)
    if len(json.dumps(out, ensure_ascii=False).encode()) > MAX_BYTES:
        raise ContentError("The content is too large (over 3 MB). Use smaller photos.")
    return out


# ---------- read ----------

def default() -> dict:
    data = _read(DEFAULT_FILE)
    if data is None:
        raise RuntimeError(f"Missing {DEFAULT_FILE}")
    return data


def published() -> dict:
    with _lock:
        found = _read(PUBLISHED)
        if found:
            return found
        d = default()
        return {**d, "_version": d.get("_version", 0), "_published_at": d.get("_published_at"),
                "_published_by": d.get("_published_by") or "repository default"}


def as_committed(c: dict) -> str:
    """content.json as it should be committed: clean content + who published which version, when."""
    clean = clean_content(_strip(c))
    clean.update({k: c.get(k) for k in ("_version", "_published_at", "_published_by")})
    return json.dumps(clean, ensure_ascii=False, indent=1)


def draft() -> dict:
    with _lock:
        d = _read(DRAFT)
        if d is None:
            d = copy.deepcopy(published())
            d["_rev"] = 0
        return d


def is_dirty() -> bool:
    d = _read(DRAFT)
    if d is None:
        return False
    return _strip(d) != _strip(published())


def _strip(c: dict) -> dict:
    return {k: v for k, v in c.items() if not k.startswith("_")}


def photo_hash(photo: str) -> str:
    return hashlib.sha1(photo.encode()).hexdigest()[:10]


def public_view(c: dict, inline_photos: bool = False) -> dict:
    """What the browser gets: hidden sections removed, photos replaced by cacheable URLs."""
    c = copy.deepcopy(_strip(c) | {"_version": c.get("_version", 0), "_published_at": c.get("_published_at")})
    if not inline_photos:
        c["sections"] = [s for s in c["sections"] if s.get("visible", True)]
    for s in c["sections"]:
        for m in s.get("members", []):
            if m.get("photo") and not inline_photos:
                m["photo"] = f"/docs/avatar/{m['id']}?v={photo_hash(m['photo'])}"
    return c


def find_photo(member_id: str) -> tuple[bytes, str] | None:
    for s in published()["sections"]:
        for m in s.get("members", []):
            if m.get("id") == member_id and m.get("photo"):
                head, data = m["photo"].split(",", 1)
                return base64.b64decode(data), head[5:].split(";")[0]
    return None


# ---------- write ----------

def save_draft(content: dict, base_rev: int | None, by: str) -> dict:
    clean = clean_content(content)
    with _lock:
        cur = draft()
        if base_rev is not None and int(base_rev) != int(cur.get("_rev", 0)):
            raise ContentError("conflict")
        clean["_rev"] = int(cur.get("_rev", 0)) + 1
        clean["_saved_at"], clean["_saved_by"] = now(), by
        _write(DRAFT, clean)
    audit(by, "save draft", f"rev {clean['_rev']}")
    return clean


def publish(by: str, note: str = "") -> dict:
    with _lock:
        d = clean_content(_strip(draft()))
        prev = published()
        version = int(prev.get("_version", 0)) + 1
        d.update(_version=version, _published_at=now(), _published_by=by, _note=_text(note, 200))
        _write(PUBLISHED, d)
        _write(VERSIONS / f"{version:04d}.json", d)
        # keep the draft in step so it is not shown as unpublished
        dr = draft()
        _write(DRAFT, {**d, "_rev": int(dr.get("_rev", 0)), "_saved_at": dr.get("_saved_at"), "_saved_by": dr.get("_saved_by")})
    audit(by, "publish", f"version {version}{': ' + note if note else ''}")
    return d


def discard_draft(by: str) -> dict:
    with _lock:
        rev = int(draft().get("_rev", 0)) + 1
        d = {**published(), "_rev": rev, "_saved_at": now(), "_saved_by": by}
        _write(DRAFT, d)
    audit(by, "discard draft")
    return d


def versions() -> list[dict]:
    out = []
    for p in sorted(VERSIONS.glob("*.json"), reverse=True):
        d = _read(p) or {}
        out.append({"version": d.get("_version"), "published_at": d.get("_published_at"),
                    "by": d.get("_published_by"), "note": d.get("_note", ""),
                    "sections": len(d.get("sections", [])), "kb": round(p.stat().st_size / 1024, 1)})
    return out


def restore(version: int, by: str) -> dict:
    data = _read(VERSIONS / f"{int(version):04d}.json")
    if data is None:
        raise ContentError(f"Version {version} was not found on this server.")
    with _lock:
        rev = int(draft().get("_rev", 0)) + 1
        d = {**_strip(data), "_rev": rev, "_saved_at": now(), "_saved_by": by}
        _write(DRAFT, d)
    audit(by, "restore into draft", f"version {version}")
    return d


def reset_to_default(by: str) -> dict:
    with _lock:
        rev = int(draft().get("_rev", 0)) + 1
        d = {**clean_content(default()), "_rev": rev, "_saved_at": now(), "_saved_by": by}
        _write(DRAFT, d)
    audit(by, "reset draft to repository default")
    return d


def storage_info() -> dict:
    return {"dir": str(DATA_DIR), "custom_dir": bool(os.getenv("DOCS_DATA_DIR")),
            "on_render": bool(os.getenv("RENDER")), "default_file": str(DEFAULT_FILE.relative_to(config.ROOT))}
