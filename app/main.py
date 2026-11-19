"""Protishruti API.

Run locally:  uvicorn app.main:app --reload
Open:         http://localhost:8000
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from starlette.concurrency import run_in_threadpool

from .redact import redact
from . import asr, config, docreader, explain, extract, record, rules, whatsapp
from .schema import CheckResult, Promise

app = FastAPI(title="Protishruti", version="0.1.0")
app.include_router(whatsapp.router)
FRONTEND = Path(__file__).resolve().parent.parent / "frontend" / "index.html"
log = logging.getLogger("protishruti")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


async def _step(label: str, fn, *args, **kwargs):
    """Run a slow (model) step off the event loop and log how long it took."""
    t = time.perf_counter()
    log.info("%s ...", label)
    out = await run_in_threadpool(fn, *args, **kwargs)
    log.info("%s done in %.1fs", label, time.perf_counter() - t)
    return out


@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception):
    """Always answer in JSON so the page can show the reason; the full traceback goes to the terminal."""
    log.exception("Unhandled error on %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": f"Server error: {type(exc).__name__}: {exc}"[:500]})


def _read_safely(data: bytes, filename: str, mime: str | None, hint: str | None = None) -> Promise:
    """One unreadable document must not break the whole check."""
    try:
        return docreader.read_document(data, filename, mime, hint=hint)
    except Exception as e:  # API key, quota, network, model output...
        log.exception("Could not read %s", filename)
        name = (filename or "").lower()
        guess = next((t for t in ("visa", "payslip", "demand_letter", "contract") if t.split("_")[0] in name), "contract")
        src = hint if hint in docreader.DOC_TYPES else guess
        reason = f"{type(e).__name__}: {e}"[:200]
        return Promise(source=src, unreadable_fields=[f"all fields (could not read {filename}: {reason})"])


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(FRONTEND)


@app.get("/health")
def health():
    return {"ok": True, "llm_provider": config.LLM_PROVIDER, "asr_enabled": config.ASR_ENABLED, "asr_backend": config.ASR_BACKEND,
            "chain_valid": record.verify_chain()}


@app.get("/api/public-config")
def public_config():
    """What the web page needs to know: which features are switched on."""
    n = config.WA_DISPLAY_NUMBER
    return {"llm_provider": config.LLM_PROVIDER, "asr_enabled": config.ASR_ENABLED,
            "asr_backend": config.ASR_BACKEND, "chain_valid": record.verify_chain(),
            "whatsapp_number": f"+{n}" if n else None,
            "whatsapp_link": f"https://wa.me/{n}?text=%E0%A6%B8%E0%A6%BE%E0%A6%B9%E0%A6%BE%E0%A6%AF%E0%A7%8D%E0%A6%AF" if n else None}


@app.get("/api/legal")
def legal_info():
    """Cost caps + legal sources for the website's rights section and fee calculator."""
    from . import legal
    caps = json.loads((Path(__file__).resolve().parent.parent / "data" / "cost_caps.json").read_text(encoding="utf-8"))
    return {"caps": caps, "sources": [{"title": t, "url": u} for t, u in legal.LEGAL_SOURCES]}


@app.post("/api/ask")
async def ask(question: str = Form(..., max_length=500)):
    """Rights Q&A: retrieval-augmented answer from the sourced knowledge base, with citations."""
    from . import rag
    q = redact(question.strip())
    if not q:
        raise HTTPException(400, "একটি প্রশ্ন লিখুন। Write a question.")
    res = await _step("Answering a rights question", rag.answer, q)
    res["question"] = q  # as searched, with phone/passport/NID numbers masked
    return res


@app.get("/api/ask/topics")
def ask_topics():
    """What the knowledge base covers: topics, suggested questions, sections and sources."""
    from . import rag
    idx = rag.get_index()
    return {"topics": rag.topics(), "passages": len(idx.chunks),
            "contextual": rag.CONTEXTS_FILE.exists(), "generate": config.RAG_GENERATE and config.LLM_PROVIDER != "mock"}


@app.post("/api/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    """Speech-to-text only, so the worker can read and correct the text before the check."""
    data = await audio.read()
    try:
        heard = (await _step("Speech-to-text", asr.transcribe, data,
                             suffix=Path(audio.filename or "").suffix or ".ogg"))["text"]
    except RuntimeError as e:
        raise HTTPException(400, str(e))
    log.info("Heard: %s", heard)
    return {"text": redact(heard)}


@app.post("/api/check", response_model=CheckResult)
async def check(
    transcript: Optional[str] = Form(None, description="Voice-note transcript (if no audio)"),
    from_voice: bool = Form(False, description="The transcript came from speech-to-text"),
    promise_json: Optional[str] = Form(None, description="Promise fields as JSON (testing)"),
    audio: Optional[UploadFile] = File(None),
    documents: list[UploadFile] = File(default_factory=list),
    payslips: list[UploadFile] = File(default_factory=list),
):
    attachments: dict[str, bytes] = {}

    # 1. Promise: from audio, transcript or JSON. A transcript the worker checked wins over
    # re-transcribing the audio; the audio is still kept in the record.
    if audio is not None and audio.filename:
        data = await audio.read()
        attachments[f"audio:{audio.filename}"] = data
    if audio is not None and audio.filename and not (transcript or "").strip():
        try:
            heard = (await _step("Speech-to-text", asr.transcribe, data, suffix=Path(audio.filename).suffix or ".ogg"))["text"]
            log.info("Heard: %s", heard)
            if heard:
                transcript, from_voice = heard, True
        except RuntimeError as e:
            if not transcript:
                raise HTTPException(400, str(e))
    if promise_json:
        try:
            promise = Promise.model_validate(json.loads(promise_json))
        except ValueError as e:
            raise HTTPException(400, f"promise_json is not valid: {e}"[:300])
    elif transcript:
        promise = await _step("Reading the promise", extract.extract_promise, transcript, from_voice=from_voice)
    else:
        raise HTTPException(400, "Send audio, a transcript, or promise_json.")

    # 2. Documents and payslips
    docs, slips = [], []
    for up in documents:
        b = await up.read()
        attachments[f"doc:{up.filename}"] = b
        docs.append(await _step(f"Reading {up.filename}", _read_safely, b, up.filename, up.content_type))
    for up in payslips:
        b = await up.read()
        attachments[f"payslip:{up.filename}"] = b
        slips.append(await _step(f"Reading {up.filename}", _read_safely, b, up.filename, up.content_type, hint="payslip"))
    slips += [d for d in docs if d.source == "payslip"]  # a payslip uploaded as a document
    docs = [d for d in docs if d.source != "payslip"]

    # 3. Rules decide; 4. AI explains
    flags = rules.run_rules(promise, docs, slips)
    missing = rules.not_checked(promise, docs)
    text = await _step("Writing the explanation", explain.explain, flags, missing)

    result = CheckResult(transcript=redact(transcript) if transcript else None, promise=promise, documents=docs, payslips=slips, flags=flags,
                         not_checked=missing, explanation_bn=text)
    # 5. Tamper-evident record
    rid, digest = record.save_record(result, attachments)
    result.record_id, result.record_hash = rid, digest
    return result


@app.get("/api/records/{record_id}", response_class=HTMLResponse)
def get_record(record_id: str):
    if not record_id.isalnum() or not (config.RECORDS_DIR / f"{record_id}.json").exists():
        raise HTTPException(404, "Record not found")
    return record.render_html(record_id)
