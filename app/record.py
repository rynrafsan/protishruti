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


SEVERITY_BN = {"critical": "গুরুতর", "warning": "সতর্কতা", "info": "তথ্য"}


def render_html(record_id: str) -> str:
    """Printable record page, styled like the main site (and fine on paper)."""
    body = json.loads((config.RECORDS_DIR / f"{record_id}.json").read_text(encoding="utf-8"))
    r = body["result"]
    e = html.escape
    flags = "".join(
        f"""<div class="flag {e(f['severity'])}"><div class="sev">{e(SEVERITY_BN.get(f['severity'], f['severity']))}
        <small>{e(f['rule_id'])}</small></div><div><b>{e(f['title_bn'])}</b><br><span class="en">{e(f['title_en'])}</span>
        <dl>{f"<dt>যা বলা হয়েছিল</dt><dd>{e(str(f['promised']))}</dd>" if f.get('promised') else ''}
        {f"<dt>যা পাওয়া গেছে</dt><dd>{e(str(f['found']))}</dd>" if f.get('found') else ''}
        <dt>সূত্র</dt><dd>{e(f['source'])}</dd>
        {f"<dt>আইন কী বলে</dt><dd>{e(f['law_bn'])}</dd>" if f.get('law_bn') else ''}
        {f"<dt>এখন যা করবেন</dt><dd>{e(f['action_bn'])}</dd>" if f.get('action_bn') else ''}
        {("<dt>যাচাই করা সূত্র</dt><dd>" + "; ".join(f"{e(r['section'])} ({e(r['source'])})" for r in f.get('refs', [])) + "</dd>") if f.get('refs') else ''}</dl></div></div>"""
        for f in r["flags"]) or "<p>দেখানো কাগজে অমিল পাওয়া যায়নি। এর মানে চাকরিটি নিরাপদ, তা নয়।</p>"
    atts = "".join(f"<li>{e(n)}<code>{h}</code></li>" for n, h in body["attachments_sha256"].items())
    heard = (f"<h2>যা শোনা বা পড়া হয়েছে</h2><blockquote>{e(r['transcript'])}</blockquote>"
             if r.get("transcript") else "")
    return f"""<!doctype html><html lang="bn"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>প্রতিশ্রুতি রেকর্ড {e(record_id)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Hind+Siliguri:wght@400;600;700&family=IBM+Plex+Mono:wght@500&family=Tiro+Bangla&display=swap" rel="stylesheet">
<style>
:root{{--green:#0E4B3B;--paper:#F7F9F6;--ink:#1F2D28;--muted:#5B6B65;--line:#CFD9D3;--red:#C0262D;--violet:#5D3A9B;--gold:#C8A456}}
*{{box-sizing:border-box}}body{{margin:0;background:#E9EFEB;color:var(--ink);font:16px/1.65 'Hind Siliguri','Noto Sans Bengali',system-ui,sans-serif}}
.sheet{{max-width:860px;margin:24px auto;background:var(--paper);border:1px solid var(--line);position:relative;overflow:hidden}}
.sheet::after{{content:'PROTOTYPE · SYNTHETIC DATA';position:absolute;top:42%;left:-10%;right:-10%;text-align:center;transform:rotate(-18deg);
font:700 64px/1 'Hind Siliguri',sans-serif;color:rgba(192,38,45,.07);pointer-events:none}}
header{{background:var(--green);color:#fff;padding:22px 28px;display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap;align-items:end}}
header .logo{{flex:none;align-self:center;border-radius:11px;box-shadow:0 0 0 1px rgba(200,164,86,.45)}}header h1{{font:400 30px/1.2 'Tiro Bangla',serif;margin:0}}header p{{margin:2px 0 0;color:#cfe1d8;font-size:14px}}
.id{{font:500 13px/1.4 'IBM Plex Mono',monospace;color:var(--gold);text-align:right}}
main{{padding:8px 28px 28px}}h2{{font:400 21px/1.3 'Tiro Bangla',serif;margin:26px 0 10px;color:var(--green)}}
.note{{background:#fff;border:1px dashed var(--red);color:var(--red);padding:8px 12px;font-size:14px;margin-top:18px}}
.flag{{display:grid;grid-template-columns:96px 1fr;gap:14px;border-left:5px solid var(--line);background:#fff;padding:12px 14px;margin:10px 0}}
.flag.critical{{border-color:var(--red)}}.flag.warning{{border-color:var(--violet)}}.flag.info{{border-color:var(--green)}}
.sev{{font-weight:700}}.critical .sev{{color:var(--red)}}.warning .sev{{color:var(--violet)}}.info .sev{{color:var(--green)}}
.sev small{{display:block;font:500 12px 'IBM Plex Mono',monospace;color:var(--muted)}}.en{{color:var(--muted);font-size:14px}}
dl{{display:grid;grid-template-columns:max-content 1fr;gap:2px 12px;margin:8px 0 0;font-size:14px}}dt{{color:var(--muted)}}dd{{margin:0}}
blockquote{{margin:0;padding:10px 14px;border-left:3px solid var(--gold);background:#fff}}
pre{{white-space:pre-wrap;font:inherit;background:#fff;border:1px solid var(--line);padding:14px;margin:0}}
ul{{padding-left:20px}}li code,.hash code{{display:block;font:500 12px/1.5 'IBM Plex Mono',monospace;word-break:break-all;color:var(--muted)}}
.hash{{border-top:2px dashed var(--line);margin-top:26px;padding-top:14px}}
.actions{{margin-top:18px}}button{{font:600 15px 'Hind Siliguri',sans-serif;background:var(--green);color:#fff;border:0;padding:10px 18px;cursor:pointer}}
@media print{{body{{background:#fff}}.sheet{{margin:0;border:0}}.actions{{display:none}}header{{-webkit-print-color-adjust:exact;print-color-adjust:exact}}}}
@media (max-width:560px){{header,main{{padding-left:16px;padding-right:16px}}.flag{{grid-template-columns:1fr}}}}
</style></head><body><div class="sheet">
<header><img class="logo" src="/brand/icon.svg" width="48" height="48" alt=""><div style="flex:1"><h1>প্রতিশ্রুতি রেকর্ড</h1><p>Protishruti Record. Legal information, not legal advice.</p></div>
<div class="id">{e(record_id)}<br>{e(body['created_utc'])} UTC</div></header>
<main><p class="note">প্রোটোটাইপ: শুধু নমুনা (SYNTHETIC) তথ্য। Prototype with synthetic data only.</p>
{heard}<h2>অমিল ও সতর্কতা</h2>{flags}
<h2>সহজ ভাষায় ব্যাখ্যা</h2><pre>{e(r['explanation_bn'])}</pre>
<h2>যা যাচাই করা যায়নি</h2><ul>{''.join(f'<li>{e(x)}</li>' for x in r['not_checked'])}</ul>
<h2>প্রমাণের আঙুলের ছাপ</h2><ul>{atts or '<li>কোনো ফাইল নেই · no files</li>'}</ul>
<div class="hash"><b>রেকর্ড হ্যাশ (SHA-256)</b><code>{e(body['hash'])}</code>
<b>আগের রেকর্ডের হ্যাশ</b><code>{e(body['prev_hash'])}</code>
<p class="en">প্রতিটি রেকর্ড আগেরটির হ্যাশের সাথে জোড়া। পরে কেউ বদলালে হিসাব মিলবে না।
Each record is chained to the previous one, so a later change breaks the chain.</p></div>
<div class="actions"><button onclick="print()">প্রিন্ট বা PDF সেভ করুন</button></div>
</main></div></body></html>"""
