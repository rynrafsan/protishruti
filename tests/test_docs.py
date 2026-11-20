"""The live /docs module: visibility schedule, admin access, editing, publishing, safety of stored HTML."""
from datetime import datetime, timedelta
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.docsite import auth, settings, store
from app.docsite.sanitize import clean_html, to_markdown
from app.main import app

ADMIN, SUPER = "admin-password-123", "super-password-123"
H = {"X-Docs-Admin": "1"}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "FILE", tmp_path / "settings.json")
    monkeypatch.setattr(settings, "COMMITTED", tmp_path / "committed-settings.json")
    for name in ("PUBLISHED", "DRAFT", "AUDIT"):
        monkeypatch.setattr(store, name, tmp_path / getattr(store, name).name)
    monkeypatch.setattr(store, "VERSIONS", tmp_path / "versions")
    monkeypatch.setenv("DOCS_ADMIN_PASSWORD", ADMIN)
    monkeypatch.setenv("DOCS_SUPERADMIN_PASSWORD", SUPER)
    for var in ("DOCS_PUBLIC", "DOCS_SCHEDULE", "DOCS_OPEN_FROM", "DOCS_OPEN_UNTIL", "DOCS_GITHUB_TOKEN"):
        monkeypatch.delenv(var, raising=False)
    auth._fails.clear()
    auth._all_fails.clear()
    return TestClient(app)


def login(c, pw=ADMIN):
    r = c.post("/api/docs/admin/login", json={"password": pw, "name": "Tester"}, headers=H)
    assert r.status_code == 200, r.text
    return r


def at(text):
    return datetime.fromisoformat(text).replace(tzinfo=settings.BD)


# ---------- schedule ----------

def test_schedule_states():
    s = {"enabled": True, "schedule": True, "start": "2026-06-10T00:00+06:00", "end": "2026-06-14T23:59+06:00", "closed_message": "x"}
    assert settings.status(at("2026-06-09T23:59"), s)["state"] == "scheduled"
    assert settings.status(at("2026-06-12T10:00"), s)["open"] is True
    assert settings.status(at("2026-06-14T23:59:30"), s)["open"] is True  # the end minute is included
    assert settings.status(at("2026-06-15T00:00"), s)["state"] == "ended"
    assert settings.status(at("2026-06-12T10:00"), {**s, "enabled": False})["state"] == "off"
    assert settings.status(at("2027-01-01T00:00"), {**s, "schedule": False})["open"] is True


def test_settings_validation(client):
    with pytest.raises(ValueError):
        settings.save({"start": "2026-12-02T10:00", "end": "2026-12-01T10:00"}, "t")
    s = settings.save({"duration_hours": 24}, "t")
    start, end = settings.parse_time(s["start"]), settings.parse_time(s["end"])
    assert end - start == timedelta(hours=24) and s["enabled"] and s["schedule"]


# ---------- gate ----------

def test_closed_docs_return_403_but_admins_still_see_them(client):
    login(c := client)
    assert c.put("/api/docs/admin/settings", json={"enabled": False}, headers=H).status_code == 200
    anon = TestClient(app)
    r = anon.get("/docs")
    assert r.status_code == 403 and "not available" in r.text and "Problem" not in r.text
    for path in ("/api/docs/content", "/api/docs/live", "/docs/export.md"):
        assert anon.get(path).status_code == 403, path
    assert c.get("/docs").status_code == 200  # signed-in admin
    c.put("/api/docs/admin/settings", json={"enabled": True, "schedule": False}, headers=H)
    assert anon.get("/docs").status_code == 200


def test_open_docs_page_and_exports(client):
    r = client.get("/docs")
    assert r.status_code == 200 and 'id="boot"' in r.text
    assert "</script><script" not in r.text.split('id="boot"')[1].split("</script>")[0]
    md = client.get("/docs/export.md")
    assert md.status_code == 200 and md.text.startswith("# Protishruti") and "```mermaid" in md.text
    assert client.get("/api/docs").status_code == 200  # Swagger moved to /api/docs


def test_live_snapshot_reads_the_running_app(client):
    j = client.get("/api/docs/live").json()
    paths = {e["path"] for e in j["endpoints"]}
    assert {"/api/check", "/api/ask", "/health"} <= paths
    assert not any(p.startswith("/api/docs/admin") for p in paths)  # admin API stays out of the public list
    assert any(f["name"].startswith("Rules engine (12 rules)") for f in j["features"])
    assert j["knowledge"]["passages"] > 0 and j["system"]["accounts"] == 0


# ---------- admin access ----------

def test_sign_in_rules(client, monkeypatch):
    assert client.post("/api/docs/admin/login", json={"password": ADMIN}).status_code == 403  # no CSRF header
    assert client.post("/api/docs/admin/login", json={"password": "nope"}, headers=H).status_code == 401
    assert client.put("/api/docs/admin/settings", json={"enabled": False}, headers=H).status_code == 401
    login(client)
    assert client.put("/api/docs/admin/settings", json={"enabled": True}).status_code == 403  # CSRF header missing
    assert client.post("/api/docs/admin/reset-content", headers=H).status_code == 403  # Admin is not Super Admin
    monkeypatch.setenv("DOCS_ADMIN_PASSWORD", "short")  # under 12 characters: ignored
    assert client.post("/api/docs/admin/login", json={"password": "short"}, headers=H).status_code == 401


def test_too_many_wrong_passwords(client):
    for _ in range(auth.PER_IP):
        client.post("/api/docs/admin/login", json={"password": "wrong-password"}, headers=H)
    assert client.post("/api/docs/admin/login", json={"password": ADMIN}, headers=H).status_code == 429


# ---------- editing ----------

def test_draft_publish_conflict_and_restore(client):
    login(client, SUPER)
    d = client.get("/api/docs/admin/draft").json()["content"]
    d["sections"][0]["body"] = "<p>Changed by the test</p>"
    r = client.put("/api/docs/admin/draft", json={"content": d, "base_rev": d["_rev"]}, headers=H)
    assert r.status_code == 200
    stale = client.put("/api/docs/admin/draft", json={"content": d, "base_rev": d["_rev"]}, headers=H)
    assert stale.status_code == 409
    assert "Changed by the test" not in client.get("/api/docs/content").text  # not public before publishing
    p = client.post("/api/docs/admin/publish", json={"note": "test"}, headers=H).json()
    assert p["version"] == 1 and "Changed by the test" in client.get("/api/docs/content").text
    assert client.post("/api/docs/admin/reset-content", headers=H).status_code == 200
    assert client.post("/api/docs/admin/versions/1/restore", headers=H).status_code == 200
    assert "Changed by the test" in client.get("/api/docs/admin/draft").text
    assert client.get("/api/docs/admin/audit").json()["entries"][0]["action"] == "restore into draft"


def test_hidden_sections_and_bad_input(client):
    login(client)
    d = client.get("/api/docs/admin/draft").json()["content"]
    d["sections"][1]["visible"] = False
    hidden_id = d["sections"][1]["id"]
    client.put("/api/docs/admin/draft", json={"content": d}, headers=H)
    client.post("/api/docs/admin/publish", json={}, headers=H)
    assert hidden_id not in {s["id"] for s in TestClient(app).get("/api/docs/content").json()["sections"]}
    team = next(s for s in d["sections"] if s["type"] == "team")
    team["members"].append({"name": "X", "role": "Y", "email": "not-an-email"})
    assert client.put("/api/docs/admin/draft", json={"content": d}, headers=H).status_code == 400


def test_photo_upload_is_resized_and_stripped(client):
    login(client)
    buf = BytesIO()
    im = Image.new("RGB", (1200, 900), (10, 120, 80))
    exif = im.getexif()
    exif[0x010F] = "Camera maker"
    im.save(buf, "JPEG", exif=exif)
    r = client.post("/api/docs/admin/photo", files={"file": ("me.jpg", buf.getvalue(), "image/jpeg")}, headers=H)
    assert r.status_code == 200
    import base64
    out = Image.open(BytesIO(base64.b64decode(r.json()["photo"].split(",", 1)[1])))
    assert out.size == (300, 400) and out.format == "WEBP" and not out.getexif()
    bad = client.post("/api/docs/admin/photo", files={"file": ("x.jpg", b"not an image", "image/jpeg")}, headers=H)
    assert bad.status_code == 400


# ---------- stored HTML is safe ----------

def test_sanitizer_removes_scripts_and_handlers():
    dirty = ('<p onclick="x()">Hi <b>there</b><script>alert(1)</script></p><a href="javascript:alert(1)">bad</a>'
             '<a href="https://example.org" onmouseover="x">ok</a><img src=x onerror=alert(1)><h1>Title</h1>')
    clean = clean_html(dirty)
    assert "script" not in clean and "onclick" not in clean and "javascript" not in clean and "<img" not in clean
    assert "<strong>there</strong>" in clean and '<a href="https://example.org">ok</a>' in clean and "<h3>Title</h3>" in clean


def test_markdown_export_of_lists_tables_links():
    md = to_markdown(clean_html('<h3>Head</h3><ul><li>One <a href="https://a.b">link</a></li><li>Two</li></ul>'
                                '<table><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></table>'))
    assert "### Head" in md and "- One [link](https://a.b)" in md and "| A | B |" in md and "| 1 | 2 |" in md


# ---------- GitHub sync (makes admin changes survive restarts on hosts without a disk) ----------

def test_publish_commits_to_github_when_configured(client, monkeypatch):
    import base64
    import json as _json

    import httpx
    from app.docsite import github
    calls = []

    def handler(request: httpx.Request):
        calls.append((request.method, request.url.path, request.headers.get("authorization")))
        if request.method == "GET":
            return httpx.Response(404, json={"message": "Not Found"})
        body = _json.loads(request.content)
        assert body["branch"] == "main" and "publish version 1" in body["message"]
        assert _json.loads(base64.b64decode(body["content"]))["_version"] == 1
        return httpx.Response(201, json={"commit": {"sha": "abc1234def", "html_url": "https://github.com/x/y/commit/abc"}})

    real = httpx.Client
    monkeypatch.setattr(github.httpx, "Client", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    monkeypatch.setenv("DOCS_GITHUB_REPO", "owner/repo")
    monkeypatch.setenv("DOCS_GITHUB_TOKEN", "test-token")
    login(client)
    r = client.post("/api/docs/admin/publish", json={"note": "sync"}, headers=H).json()
    assert r["github"] == {"ok": True, "commit": "abc1234", "url": "https://github.com/x/y/commit/abc"}
    assert calls[1][:2] == ("PUT", "/repos/owner/repo/contents/data/docs/content.json") and calls[1][2] == "Bearer test-token"
