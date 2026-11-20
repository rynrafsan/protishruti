"""HTTP routes for the live /docs module."""
from __future__ import annotations

import html
import json
from datetime import datetime

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse, Response

from .. import config
from . import auth, github, images, live, settings, store
from .sanitize import plain, to_markdown

router = APIRouter(include_in_schema=False)
PAGES = config.ROOT / "frontend" / "docs"
NOINDEX = {"X-Robots-Tag": "noindex, nofollow", "Cache-Control": "no-store"}


def _gate(request: Request) -> tuple[dict, dict | None]:
    """Status and the signed-in admin. Raises 403 when /docs is closed to this visitor."""
    st = settings.status()
    who = auth.current(request)
    if not st["open"] and not who:
        raise HTTPException(403, {"message": st["closed_message"], "status": st})
    return st, who


def _fmt(ts: str | None) -> str:
    if not ts:
        return ""
    dt = settings.parse_time(ts).astimezone(settings.BD)
    return dt.strftime("%d %b %Y, %I:%M %p") + " (Bangladesh time, GMT+6)"


def _closed_page(st: dict) -> HTMLResponse:
    when = {"scheduled": f"Opens {_fmt(st['start'])}.", "ended": f"Closed {_fmt(st['end'])}.",
            "off": "Turned off by the team."}.get(st["state"], "")
    page = (PAGES / "closed.html").read_text(encoding="utf-8")
    page = page.replace("{{message}}", html.escape(st["closed_message"])).replace("{{when}}", html.escape(when))
    return HTMLResponse(page, status_code=403, headers=NOINDEX)


def _boot(data: dict) -> str:
    # JSON inside <script>: escape "<" so "</script>" in content cannot end the tag
    return json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")


@router.get("/docs/")
def docs_slash():
    return RedirectResponse("/docs", status_code=308)


@router.get("/docs", response_class=HTMLResponse)
def docs_page(request: Request, preview: str = ""):
    st = settings.status()
    who = auth.current(request)
    if not st["open"] and not who:
        return _closed_page(st)
    draft = preview == "draft" and who is not None
    content = store.draft() if draft else store.published()
    view = store.public_view(content, inline_photos=draft)
    boot = {"content": view, "status": st, "admin": who, "preview": draft}
    page = (PAGES / "index.html").read_text(encoding="utf-8")
    meta = view["meta"]
    page = (page.replace("{{title}}", html.escape(f"{meta['title']} — docs"))
                .replace("{{description}}", html.escape(meta.get("tagline", "")))
                .replace("<!--BOOT-->", f'<script id="boot" type="application/json">{_boot(boot)}</script>'))
    headers = {"Cache-Control": "no-store"}
    if draft or not st["open"]:
        headers["X-Robots-Tag"] = "noindex, nofollow"
    return HTMLResponse(page, headers=headers)


@router.get("/docs/admin", response_class=HTMLResponse)
def admin_page():
    return HTMLResponse((PAGES / "admin.html").read_text(encoding="utf-8"), headers=NOINDEX)


@router.get("/docs/export.md")
def export_markdown(request: Request):
    _gate(request)
    c = store.public_view(store.published())
    meta = c["meta"]
    out = [f"# {meta['title']}", "", f"_{meta['tagline']}_", "", to_markdown(meta.get("summary", "")), ""]
    groups = {"pitch": "Pitch deck", "tech": "Technical documentation"}
    for g, label in groups.items():
        out += [f"## {label}", ""]
        for s in (x for x in c["sections"] if x["group"] == g):
            out += [f"### {s['title']}", ""]
            if s.get("kicker"):
                out += [f"**{s['kicker']}**", ""]
            for f in s.get("figures", []):
                out.append(f"- **{f['value']}** — {f['label']}" + (f" ([source]({f['source']}))" if f.get("source") else ""))
            if s.get("figures"):
                out.append("")
            body = to_markdown(s.get("body", ""))
            if body:
                out += [body.replace("\n### ", "\n#### "), ""]
            if s["type"] == "team":
                if s.get("team_name"):
                    out += [f"Team: **{s['team_name']}**", ""]
                for m in s.get("members", []):
                    out.append(f"- **{m['name']}** — {m['role']}" + (f" · <{m['email']}>" if m.get("email") else ""))
                out.append("")
            if s["type"] == "diagram" and s.get("mermaid"):
                out += ["```mermaid", s["mermaid"].strip(), "```", ""]
                if s.get("caption"):
                    out += [f"_{s['caption']}_", ""]
            if s["type"] == "changelog":
                for e in s.get("entries", []):
                    out += [f"#### {e['version']} — {e['date']}", "", to_markdown(e.get("notes", "")), ""]
            for p in s.get("planned", []):
                out.append(f"- {p['name']} ({p['status']}){': ' + p['note'] if p.get('note') else ''}")
            if s.get("planned"):
                out.append("")
            if s.get("live"):
                out += [f"_Live data for this section: {str(request.base_url).rstrip('/')}/docs#{s['id']}_", ""]
    out.append(f"_Exported {datetime.now(settings.BD).strftime('%d %b %Y %H:%M')} (GMT+6) from version {c.get('_version', 0)}._")
    return PlainTextResponse("\n".join(out), media_type="text/markdown; charset=utf-8",
                             headers={"Content-Disposition": 'attachment; filename="protishruti-docs.md"'})


@router.get("/docs/avatar/{member_id}")
def avatar(member_id: str, request: Request):
    _gate(request)
    found = store.find_photo(member_id)
    if not found:
        raise HTTPException(404, "No photo")
    data, mime = found
    return Response(data, media_type=mime, headers={"Cache-Control": "public, max-age=604800, immutable"})


@router.get("/api/docs/status")
def docs_status():
    return settings.status()


@router.get("/api/docs/content")
def docs_content(request: Request):
    _gate(request)
    return store.public_view(store.published())


@router.get("/api/docs/live")
def docs_live(request: Request):
    _gate(request)
    return JSONResponse(live.snapshot(request.app), headers={"Cache-Control": "no-store"})


# ---------------- admin API ----------------

def _sync(path: str, text: str, message: str) -> dict | None:
    """Commit to GitHub when configured; a failure is reported, never fatal."""
    if not github.enabled():
        return None
    try:
        return {"ok": True, **github.commit_file(path, text, message)}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"[:300]}


def _admin_info(who: dict | None) -> dict:
    d = store.draft()
    return {"user": who, "roles_enabled": auth.roles_enabled(), "storage": store.storage_info(),
            "github": github.info(),
            "settings": settings.load(), "status": settings.status(),
            "draft_rev": d.get("_rev", 0), "dirty": store.is_dirty(),
            "published_version": store.published().get("_version", 0)}


@router.get("/api/docs/admin/me")
def admin_me(request: Request):
    return JSONResponse(_admin_info(auth.current(request)), headers=NOINDEX)


@router.post("/api/docs/admin/login")
async def admin_login(request: Request):
    if request.headers.get(auth.CSRF_HEADER) != "1":
        raise HTTPException(403, "Missing the X-Docs-Admin header.")
    if not any(auth.roles_enabled().values()):
        raise HTTPException(503, "Admin sign-in is off: set DOCS_ADMIN_PASSWORD (12+ characters) on the server.")
    body = await request.json()
    name = plain(str(body.get("name") or ""), 40)
    role = auth.check_password(str(body.get("password") or ""), auth.client_ip(request))
    if not role:
        raise HTTPException(401, "Wrong password.")
    name = name or ("Super Admin" if role == "super" else "Admin")
    resp = JSONResponse({"role": role, "name": name})
    resp.set_cookie(auth.COOKIE, auth.make_token(role, name), max_age=auth.SESSION_S, httponly=True,
                    samesite="strict", secure=auth.is_https(request), path="/")
    store.audit(name, "sign in", role)
    return resp


@router.post("/api/docs/admin/logout")
def admin_logout(request: Request):
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(auth.COOKIE, path="/")
    return resp


@router.put("/api/docs/admin/settings")
async def admin_settings(request: Request):
    who = auth.require(request)
    try:
        s = settings.save(await request.json(), who["name"])
    except (ValueError, TypeError) as e:
        raise HTTPException(400, str(e))
    store.audit(who["name"], "change visibility", json.dumps({k: s[k] for k in ("enabled", "schedule", "start", "end")}))
    synced = _sync("data/docs/settings.json", json.dumps(settings.public_fields(s), ensure_ascii=False, indent=1),
                   f"docs: visibility {'on' if s['enabled'] else 'off'}, window {s['start']} to {s['end']} (by {who['name']})")
    return {"settings": s, "status": settings.status(), "github": synced}


@router.post("/api/docs/admin/settings/reset")
def admin_settings_reset(request: Request):
    who = auth.require(request, "super")
    s = settings.reset()
    store.audit(who["name"], "reset visibility to environment defaults")
    return {"settings": s, "status": settings.status()}


@router.get("/api/docs/admin/draft")
def admin_draft(request: Request):
    auth.require(request)
    return JSONResponse({"content": store.draft(), "dirty": store.is_dirty()}, headers=NOINDEX)


@router.put("/api/docs/admin/draft")
async def admin_save_draft(request: Request):
    who = auth.require(request)
    body = await request.json()
    try:
        d = store.save_draft(body.get("content") or {}, body.get("base_rev"), who["name"])
    except store.ContentError as e:
        if str(e) == "conflict":
            raise HTTPException(409, "Someone else saved this draft after you opened it. Reload to see their changes.")
        raise HTTPException(400, str(e))
    return {"rev": d["_rev"], "saved_at": d["_saved_at"], "dirty": store.is_dirty()}


@router.post("/api/docs/admin/publish")
async def admin_publish(request: Request):
    who = auth.require(request)
    body = await request.json()
    try:
        p = store.publish(who["name"], str(body.get("note") or ""))
    except store.ContentError as e:
        raise HTTPException(400, str(e))
    synced = _sync("data/docs/content.json", store.as_committed(p),
                   f"docs: publish version {p['_version']} (by {who['name']})" + (f": {p['_note']}" if p.get("_note") else ""))
    return {"version": p["_version"], "published_at": p["_published_at"], "github": synced}


@router.post("/api/docs/admin/discard")
def admin_discard(request: Request):
    who = auth.require(request)
    d = store.discard_draft(who["name"])
    return {"rev": d["_rev"]}


@router.get("/api/docs/admin/versions")
def admin_versions(request: Request):
    auth.require(request)
    return {"versions": store.versions()}


@router.post("/api/docs/admin/versions/{version}/restore")
def admin_restore(version: int, request: Request):
    who = auth.require(request, "super")
    try:
        d = store.restore(version, who["name"])
    except store.ContentError as e:
        raise HTTPException(404, str(e))
    return {"rev": d["_rev"]}


@router.post("/api/docs/admin/reset-content")
def admin_reset_content(request: Request):
    who = auth.require(request, "super")
    d = store.reset_to_default(who["name"])
    return {"rev": d["_rev"]}


@router.post("/api/docs/admin/photo")
async def admin_photo(request: Request, file: UploadFile = File(...)):
    auth.require(request)
    data = await file.read(images.MAX_UPLOAD + 1)
    try:
        uri = images.avatar_data_uri(data)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"photo": uri, "kb": round(len(uri) * 3 / 4 / 1024, 1)}


@router.get("/api/docs/admin/export.json")
def admin_export(request: Request, which: str = "draft"):
    auth.require(request)
    c = store.draft() if which == "draft" else store.published()
    clean = store.clean_content({k: v for k, v in c.items() if not k.startswith("_")})
    return Response(json.dumps(clean, ensure_ascii=False, indent=1), media_type="application/json",
                    headers={"Content-Disposition": 'attachment; filename="content.json"', **NOINDEX})


@router.get("/api/docs/admin/audit")
def admin_audit(request: Request):
    auth.require(request, "super")
    return {"entries": store.audit_log()}
