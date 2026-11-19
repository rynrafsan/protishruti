"""WhatsApp Cloud API channel (Phase 2).

Flow: worker sends voice notes / text (the promise) and photos (documents), then types "check".
Meta requires the webhook to answer within ~10 s, so we reply 200 at once and do the work
in a background task, then send the result as a new message.

Setup (see README, Phase 2): create a Meta app, add WhatsApp, use the free test number
(up to 5 verified recipients), set WA_VERIFY_TOKEN / WA_ACCESS_TOKEN / WA_PHONE_NUMBER_ID,
and point the webhook to https://<your-domain>/whatsapp/webhook.
Sessions are kept in memory here; use Redis or Postgres in production.
"""
from __future__ import annotations

import os
from collections import defaultdict

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import PlainTextResponse

from . import asr, docreader, explain, extract, record, rules
from .schema import CheckResult, Promise

router = APIRouter(prefix="/whatsapp")
VERIFY_TOKEN = os.getenv("WA_VERIFY_TOKEN", "")
ACCESS_TOKEN = os.getenv("WA_ACCESS_TOKEN", "")
PHONE_ID = os.getenv("WA_PHONE_NUMBER_ID", "")
GRAPH = f"https://graph.facebook.com/{os.getenv('WA_API_VERSION', 'v22.0')}"

SESSIONS: dict[str, dict] = defaultdict(lambda: {"transcripts": [], "docs": [], "attachments": {}})
HELP = ("প্রতিশ্রুতি (প্রোটোটাইপ)। ১) দালাল কী বলেছে তা ভয়েস বা লিখে পাঠান। "
        "২) ভিসা/চুক্তির ছবি পাঠান। ৩) 'check' লিখুন। শুধু নমুনা (SPECIMEN) কাগজ ব্যবহার করুন।")


@router.get("/webhook")
def verify(request: Request):
    q = request.query_params
    if q.get("hub.mode") == "subscribe" and VERIFY_TOKEN and q.get("hub.verify_token") == VERIFY_TOKEN:
        return PlainTextResponse(q.get("hub.challenge", ""))
    raise HTTPException(403, "verification failed")


@router.post("/webhook")
async def receive(request: Request, background: BackgroundTasks):
    body = await request.json()
    for entry in body.get("entry", []):
        for change in entry.get("changes", []):
            for msg in change.get("value", {}).get("messages", []):
                background.add_task(handle_message, msg)
    return {"ok": True}  # answer fast; work happens in the background


async def send_text(to: str, text: str):
    async with httpx.AsyncClient(timeout=30) as c:
        await c.post(f"{GRAPH}/{PHONE_ID}/messages",
                     headers={"Authorization": f"Bearer {ACCESS_TOKEN}"},
                     json={"messaging_product": "whatsapp", "to": to, "type": "text",
                           "text": {"body": text[:4000]}})


async def download_media(media_id: str) -> tuple[bytes, str]:
    async with httpx.AsyncClient(timeout=60) as c:
        meta = (await c.get(f"{GRAPH}/{media_id}", headers={"Authorization": f"Bearer {ACCESS_TOKEN}"})).json()
        data = await c.get(meta["url"], headers={"Authorization": f"Bearer {ACCESS_TOKEN}"})
        return data.content, meta.get("mime_type", "application/octet-stream")


async def handle_message(msg: dict):
    user = msg["from"]
    s = SESSIONS[user]
    kind = msg.get("type")
    try:
        if kind == "text":
            text = msg["text"]["body"].strip()
            if text.lower() in ("check", "যাচাই"):
                await run_check(user)
            elif text.lower() in ("help", "সাহায্য", "hi", "hello"):
                await send_text(user, HELP)
            else:
                s["transcripts"].append(text)
                await send_text(user, "লিখে রাখা হলো। কাগজের ছবি পাঠান, তারপর 'check' লিখুন।")
        elif kind == "audio":
            data, _ = await download_media(msg["audio"]["id"])
            s["attachments"][f"audio:{msg['audio']['id']}"] = data
            s["transcripts"].append(asr.transcribe(data)["text"])
            await send_text(user, "ভয়েস নোট পাওয়া গেছে। আমি যা বুঝেছি তা 'check' দিলে দেখাব।")
        elif kind in ("image", "document"):
            media = msg[kind]
            data, mime = await download_media(media["id"])
            s["attachments"][f"doc:{media['id']}"] = data
            s["docs"].append(docreader.read_document(data, media.get("filename", "photo.jpg"), mime))
            await send_text(user, "কাগজ পাওয়া গেছে। আরও থাকলে পাঠান, না হলে 'check' লিখুন।")
        else:
            await send_text(user, HELP)
    except Exception as e:  # never leave the user hanging
        await send_text(user, f"দুঃখিত, সমস্যা হয়েছে। আবার চেষ্টা করুন। ({type(e).__name__})")


async def run_check(user: str):
    s = SESSIONS[user]
    if not s["transcripts"]:
        await send_text(user, "আগে দালাল কী বলেছে তা পাঠান।")
        return
    promise = extract.extract_promise("\n".join(s["transcripts"]))
    docs = [d for d in s["docs"] if d.source != "payslip"]
    slips = [d for d in s["docs"] if d.source == "payslip"]
    flags = rules.run_rules(promise, docs, slips)
    missing = rules.not_checked(promise, docs)
    text = explain.explain(flags, missing)
    result = CheckResult(promise=promise, documents=docs, payslips=slips, flags=flags,
                         not_checked=missing, explanation_bn=text)
    rid, _ = record.save_record(result, s["attachments"])
    base = os.getenv("PUBLIC_BASE_URL", "")
    await send_text(user, text + (f"\n\nরেকর্ড: {base}/api/records/{rid}" if base else f"\n\nরেকর্ড আইডি: {rid}"))
