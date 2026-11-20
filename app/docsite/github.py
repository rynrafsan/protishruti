"""Optional: make admin changes permanent on hosts without a disk, by committing them to GitHub.

Render's free plan wipes the server's files on every restart, which happens whenever the free server
wakes from sleep. With these set, every publish commits data/docs/content.json, and every visibility
change commits data/docs/settings.json, to the repository. Render then redeploys with the new files.

  DOCS_GITHUB_REPO    owner/name, e.g. rynrafsan/protishruti
  DOCS_GITHUB_TOKEN   fine-grained token for that one repository, permission "Contents: Read and write"
  DOCS_GITHUB_BRANCH  default: main
"""
from __future__ import annotations

import base64
import os

import httpx

API = "https://api.github.com"


def _cfg() -> tuple[str, str, str]:
    return (os.getenv("DOCS_GITHUB_REPO", "").strip(), os.getenv("DOCS_GITHUB_TOKEN", "").strip(),
            (os.getenv("DOCS_GITHUB_BRANCH") or "main").strip())


def enabled() -> bool:
    repo, token, _ = _cfg()
    return bool(repo and token and "/" in repo)


def info() -> dict:
    repo, _, branch = _cfg()
    return {"enabled": enabled(), "repo": repo if enabled() else None, "branch": branch if enabled() else None}


def commit_file(path: str, text: str, message: str) -> dict:
    """Create or update one file. Returns {"commit": short sha, "url": ...}; raises RuntimeError."""
    repo, token, branch = _cfg()
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28"}
    url = f"{API}/repos/{repo}/contents/{path}"
    with httpx.Client(timeout=20) as client:
        r = client.get(url, params={"ref": branch}, headers=headers)
        if r.status_code not in (200, 404):
            raise RuntimeError(f"GitHub {r.status_code}: {r.text[:200]}")
        sha = r.json().get("sha") if r.status_code == 200 else None
        if sha and base64.b64decode(r.json().get("content", "")).decode("utf-8", "replace") == text:
            return {"commit": None, "url": None, "unchanged": True}
        body = {"message": message, "content": base64.b64encode(text.encode("utf-8")).decode(), "branch": branch}
        if sha:
            body["sha"] = sha
        r = client.put(url, json=body, headers=headers)
        if r.status_code not in (200, 201):
            raise RuntimeError(f"GitHub {r.status_code}: {r.text[:200]}")
        c = r.json().get("commit", {})
        return {"commit": (c.get("sha") or "")[:7], "url": c.get("html_url")}
