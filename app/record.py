"""Protishruti Record: tamper-evident evidence of what was promised and what was found.

Each record stores the SHA-256 of its canonical JSON plus the previous record's hash
(a simple hash chain). Changing any old record breaks every later hash.
Upgrade path: add an RFC 3161 trusted timestamp or OpenTimestamps proof per record.
"""
from __future__ import annotations

import hashlib
import html
import json
import uuid
from datetime import datetime, timezone

from . import config
from .schema import CheckResult

CHAIN = config.RECORDS_DIR / "chain.json"


def _canonical(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _last_hash() -> str:
    if CHAIN.exists():
        chain = json.loads(CHAIN.read_text(encoding="utf-8"))
        if chain:
            return chain[-1]["hash"]
    return "0" * 64


def save_record(result: CheckResult, attachments: dict[str, bytes]) -> tuple[str, str]:
    rid = uuid.uuid4().hex[:12]
    body = {
        "record_id": rid,
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "prev_hash": _last_hash(),
        "attachments_sha256": {name: hashlib.sha256(b).hexdigest() for name, b in attachments.items()},
        "result": result.model_dump(exclude={"record_id", "record_hash"}),
    }
    digest = hashlib.sha256(_canonical(body)).hexdigest()
    body["hash"] = digest
    (config.RECORDS_DIR / f"{rid}.json").write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")
    chain = json.loads(CHAIN.read_text(encoding="utf-8")) if CHAIN.exists() else []
    chain.append({"record_id": rid, "hash": digest, "prev_hash": body["prev_hash"]})
    CHAIN.write_text(json.dumps(chain, indent=2), encoding="utf-8")
    return rid, digest


def verify_chain() -> bool:
    if not CHAIN.exists():
        return True
    prev = "0" * 64
    for link in json.loads(CHAIN.read_text(encoding="utf-8")):
        body = json.loads((config.RECORDS_DIR / f"{link['record_id']}.json").read_text(encoding="utf-8"))
        stored = body.pop("hash")
        if body["prev_hash"] != prev or hashlib.sha256(_canonical(body)).hexdigest() != stored:
            return False
        prev = stored
    return True


def render_html(record_id: str) -> str:
    body = json.loads((config.RECORDS_DIR / f"{record_id}.json").read_text(encoding="utf-8"))
    r = body["result"]
    e = html.escape
    rows = "".join(
        f"<tr><td>{e(f['severity'])}</td><td>{e(f['title_bn'])}<br><small>{e(f['title_en'])}</small></td>"
        f"<td>{e(str(f.get('promised') or ''))}</td><td>{e(str(f.get('found') or ''))}</td><td>{e(f['source'])}</td></tr>"
        for f in r["flags"]) or "<tr><td colspan=5>No mismatch found in what was shown.</td></tr>"
    atts = "".join(f"<li>{e(n)}: <code>{h}</code></li>" for n, h in body["attachments_sha256"].items())
    return f"""<!doctype html><html lang="bn"><meta charset="utf-8">
<title>Protishruti Record {e(record_id)}</title>
<style>body{{font-family:'Noto Sans Bengali',system-ui,sans-serif;max-width:860px;margin:2rem auto;padding:0 1rem}}
table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ccc;padding:.4rem;vertical-align:top}}
.wm{{color:#b00;font-weight:700}}code{{word-break:break-all}}</style>
<h1>প্রতিশ্রুতি রেকর্ড · Protishruti Record</h1>
<p class="wm">PROTOTYPE — SYNTHETIC DATA ONLY. Legal information, not legal advice.</p>
<p>Record ID: <b>{e(record_id)}</b> · Created (UTC): {e(body['created_utc'])}</p>
<h2>Flags</h2><table><tr><th>Severity</th><th>Flag</th><th>Promised</th><th>Found</th><th>Source</th></tr>{rows}</table>
<h2>Explanation</h2><pre style="white-space:pre-wrap">{e(r['explanation_bn'])}</pre>
<h2>Not checked</h2><ul>{''.join(f'<li>{e(x)}</li>' for x in r['not_checked'])}</ul>
<h2>Evidence fingerprints</h2><ul>{atts or '<li>none</li>'}</ul>
<p>Record hash (SHA-256): <code>{e(body['hash'])}</code><br>Previous hash: <code>{e(body['prev_hash'])}</code></p>
<p><small>Print this page to PDF to keep a copy.</small></p></html>"""
