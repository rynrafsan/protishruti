"""Live system view for /docs: everything here is read from the running app, not written by hand.

- features:   what is switched on, from config + the rules registry + the knowledge base
- endpoints:  from the app's OpenAPI schema
- knowledge:  RAG passages, files, fee table, agency list, watchlist
- usage:      request counts and response times since this server started (no personal data)
- benchmarks: the rule benchmark and the RAG evaluation, re-run on this server (offline, no AI calls)
"""
from __future__ import annotations

import importlib.util
import json
import os
import platform
import random
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timezone

from .. import config
from .settings import BD

STARTED = time.time()

# ---------- usage counters ----------

EVENTS = {  # route template -> what it means to a reader
    ("POST", "/api/check"): "Promise checks",
    ("POST", "/api/ask"): "Rights questions answered",
    ("POST", "/api/transcribe"): "Voice notes transcribed",
    ("POST", "/whatsapp/webhook"): "WhatsApp messages received",
    ("GET", "/api/records/{record_id}"): "Promise Records opened",
    ("GET", "/api/legal"): "Fee-table loads",
    ("GET", "/docs"): "Docs page views",
}
_lock = threading.Lock()
_counts: dict[tuple, dict] = defaultdict(lambda: {"n": 0, "ok": 0, "client_err": 0, "server_err": 0,
                                                  "ms": deque(maxlen=400)})


def record_request(method: str, route: str, status: int, ms: float) -> None:
    if route in ("/health", "/api/docs/live") or route.startswith(("/brand", "/docs/assets")):
        return
    with _lock:
        c = _counts[(method, route)]
        c["n"] += 1
        c["ok" if status < 400 else "client_err" if status < 500 else "server_err"] += 1
        c["ms"].append(ms)


def _pct(values: list[float], p: float) -> float | None:
    if not values:
        return None
    v = sorted(values)
    return round(v[min(len(v) - 1, int(round(p * (len(v) - 1))))])


def usage() -> dict:
    with _lock:
        snap = {k: {**v, "ms": list(v["ms"])} for k, v in _counts.items()}
    events = [{"label": label, "method": m, "path": p, "count": snap.get((m, p), {}).get("ok", 0)}  # successful only
              for (m, p), label in EVENTS.items()]
    routes = sorted(({"method": m, "path": p, "count": v["n"], "errors": v["server_err"],
                      "rejected": v["client_err"], "p50_ms": _pct(v["ms"], .5), "p95_ms": _pct(v["ms"], .95)}
                     for (m, p), v in snap.items()), key=lambda r: -r["count"])
    total = sum(v["n"] for v in snap.values())
    errors = sum(v["server_err"] for v in snap.values())
    return {"since": datetime.fromtimestamp(STARTED, BD).isoformat(timespec="seconds"),
            "uptime_s": int(time.time() - STARTED), "requests": total, "server_errors": errors,
            "events": events, "routes": routes[:20]}


# ---------- features, endpoints, knowledge ----------

def _key_set() -> bool:
    p = config.LLM_PROVIDER
    return bool({"groq": config.OPENAI_API_KEY, "openai": config.OPENAI_API_KEY,
                 "gemini": config.GEMINI_API_KEY, "anthropic": config.ANTHROPIC_API_KEY}.get(p, ""))


def _ai_on() -> bool:
    return config.LLM_PROVIDER != "mock" and _key_set()


def _model() -> str:
    return {"groq": config.OPENAI_MODEL, "openai": config.OPENAI_MODEL, "gemini": config.GEMINI_MODEL,
            "anthropic": config.ANTHROPIC_MODEL}.get(config.LLM_PROVIDER, "none (offline mode)")


def _wa_on() -> bool:
    from .. import whatsapp
    return bool(whatsapp.ACCESS_TOKEN and whatsapp.PHONE_ID and whatsapp.VERIFY_TOKEN)


def features() -> list[dict]:
    from .. import legal, rag, record, rules
    n_rules = len(rules.PRE_DEPARTURE_RULES) + len(rules.POST_ARRIVAL_RULES)
    caps = rules.COST_CAPS
    idx = rag.get_index()
    ai = _ai_on()
    asr_on = config.ASR_ENABLED and (config.ASR_BACKEND != "groq" or bool(config.OPENAI_API_KEY))
    try:
        cooling = time.time() < __import__("app.llm", fromlist=["_down_until"])._down_until
    except Exception:
        cooling = False
    n_records = len([p for p in config.RECORDS_DIR.glob("*.json") if p.name != "chain.json"])
    rag_gen = ai and config.RAG_GENERATE

    def f(name, status, detail, module):
        return {"name": name, "status": status, "detail": detail, "module": module}

    return [
        f("Voice note to text (Bangla)", "live" if asr_on else "off",
          (f"Whisper {config.ASR_GROQ_MODEL} on Groq" if config.ASR_BACKEND == "groq" else f"Local model {config.ASR_MODEL}")
          if asr_on else "Switched off on this server (ASR_ENABLED=false); typed promises still work", "app/asr.py"),
        f("Promise extraction", "live" if ai and config.LLM_EXTRACT_VOICE else "fallback",
          ("AI reads voice transcripts; typed text uses the offline extractor" if not config.LLM_EXTRACT else "AI reads every transcript")
          if ai else "Offline extractor (regular expressions), no AI on this server", "app/extract.py"),
        f("Visa, contract and payslip reading", "live" if ai else "fallback",
          f"{config.LLM_PROVIDER} vision model {_model()}" if ai else "Offline mode: only JSON test documents can be read",
          "app/docreader.py"),
        f(f"Rules engine ({n_rules} rules)", "live", "R01–R12: the only part that raises a warning", "app/rules.py"),
        f("Law and next step for every warning", "live", f"{len(legal.LEGAL)} rules mapped to OEMA 2013 sections and helplines",
          "app/legal.py"),
        f("Plain-Bangla explanation", "live" if ai and config.LLM_EXPLAIN else "fallback",
          "AI-written" if ai and config.LLM_EXPLAIN else "Bangla template (saves the free AI quota)", "app/explain.py"),
        f("Rights Q&A with citations (RAG)", "live",
          f"{len(idx.chunks)} sourced passages; " + ("AI-written answers with a grounding check" if rag_gen
                                                    else "answers quoted word for word from the sources"), "app/rag.py"),
        f("Government fee calculator", "live", f"Caps for {len(caps)} countries", "data/cost_caps.json"),
        f("Tamper-evident Promise Record", "live",
          f"{n_records} records on this server; hash chain {'intact' if record.verify_chain() else 'BROKEN'}", "app/record.py"),
        f("WhatsApp channel", "live" if _wa_on() else "pilot",
          "Meta WhatsApp Cloud API webhook" if _wa_on() else "Built; not connected on this server", "app/whatsapp.py"),
        f("Identity-number masking (text)", "live", "Passport, NID and phone numbers masked before storage or AI calls",
          "app/redact.py"),
        f("AI provider health", "fallback" if cooling else ("live" if ai else "off"),
          ("Cooling down after an outage; fallbacks answer meanwhile" if cooling else f"{config.LLM_PROVIDER} · {_model()}")
          if ai else "No AI key on this server: every step uses its offline fallback", "app/llm.py"),
    ]


def endpoints(app) -> list[dict]:
    spec = app.openapi()
    out = []
    for path, ops in spec.get("paths", {}).items():
        for method, op in ops.items():
            if method not in ("get", "post", "put", "delete", "patch"):
                continue
            desc = (op.get("description") or "").strip().split("\n")[0]
            body = op.get("requestBody", {}).get("content", {})
            out.append({"method": method.upper(), "path": path, "summary": op.get("summary", ""), "description": desc,
                        "input": ", ".join(sorted(body)) or ("query" if op.get("parameters") else "—"),
                        "auth": "Meta verify token" if path.startswith("/whatsapp") and method == "get" else "None (public)"})
    order = {"GET": 0, "POST": 1}
    return sorted(out, key=lambda e: (e["path"], order.get(e["method"], 2)))


def knowledge() -> dict:
    from .. import rag, rules
    idx = rag.get_index()
    files = defaultdict(int)
    for c in idx.chunks:
        files[c.doc_title] += 1
    caps = json.loads((config.ROOT / "data" / "cost_caps.json").read_text(encoding="utf-8"))
    return {"passages": len(idx.chunks), "files": [{"title": k, "passages": v} for k, v in files.items()],
            "contextual": rag.CONTEXTS_FILE.exists(), "topics": len(rag.topics()),
            "faq": sum(len(t.get("questions", [])) for t in rag.topics()),
            "fee_countries": len(caps["caps_bdt"]), "fee_as_of": caps.get("as_of"),
            "agencies": len(rules.AGENCIES), "watchlist": len(rules.WATCHLIST),
            "vocab": len(idx.vocab)}


def system(app) -> dict:
    from .. import record
    from . import auth
    return {"version": app.version,
            "commit": (os.getenv("RENDER_GIT_COMMIT") or "")[:7] or None,
            "host": "Render" if os.getenv("RENDER") else "local",
            "python": platform.python_version(),
            "started": datetime.fromtimestamp(STARTED, BD).isoformat(timespec="seconds"),
            "ai_provider": config.LLM_PROVIDER, "ai_model": _model(), "ai_key_set": _key_set(),
            "asr": config.ASR_GROQ_MODEL if config.ASR_ENABLED and config.ASR_BACKEND == "groq" else (config.ASR_MODEL if config.ASR_ENABLED else None),
            "rag_generate": config.RAG_GENERATE, "allow_real_data": config.ALLOW_REAL_DATA, "whatsapp": _wa_on(),
            "accounts": 0, "chain_valid": record.verify_chain(), "admin_signin": any(auth.roles_enabled().values())}


# ---------- benchmarks (re-run on this server) ----------

_bench: dict = {"state": "not started"}
_bench_lock = threading.Lock()


def _load_tool(rel: str):
    path = config.ROOT / rel
    spec = importlib.util.spec_from_file_location(path.stem + "_live", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _rules_benchmark(n: int = 120, seed: int = 7) -> dict:
    from .. import rules
    from ..schema import Promise
    gen = _load_tool("tools/synth/generate.py")
    rng = random.Random(seed)
    hits, totals, false_alarms = defaultdict(int), defaultdict(int), 0
    for i in range(n):
        c = gen.make_case(i, rng)
        docs = [Promise.model_validate(c["visa"])] + ([Promise.model_validate(c["contract"])] if c["contract"] else [])
        ids = {f.rule_id for f in rules.run_rules(Promise.model_validate(c["promise"]), docs) if f.severity != "info"}
        totals[c["planted"]] += 1
        if c["planted"] == "NONE":
            false_alarms += bool(ids - {"R09"})
        elif c["planted"] in ids:
            hits[c["planted"]] += 1
    per_rule = [{"rule": r, "found": hits[r], "cases": totals[r]} for r in sorted(totals) if r != "NONE"]
    return {"cases": n, "seed": seed, "per_rule": per_rule, "clean_cases": totals["NONE"], "false_alarms": false_alarms}


def _rag_benchmark() -> dict:
    from .. import rag
    ev = _load_tool("tools/rag_eval.py")

    def score(gold):
        h1, h3, rr, ok, misses, wrong, ms = ev.run(gold)
        n = len(gold)
        return {"questions": n, "hit1": h1, "hit3": h3, "mrr": round(rr / n, 2), "key_fact": ok, "ms": round(ms)}

    return {"tuning": score(ev.GOLD), "held_out": score(ev.HELD_OUT),
            "off_topic": {"questions": len(ev.OFF_TOPIC),
                          "refused": sum(rag.answer(q, generate=False)["mode"] == "no_match" for q in ev.OFF_TOPIC)}}


def _run_benchmarks() -> None:
    t = time.perf_counter()
    try:
        result = {"rules": _rules_benchmark(), "rag": _rag_benchmark()}
        _bench.update(state="done", **result, seconds=round(time.perf_counter() - t, 1),
                      measured_at=datetime.now(BD).isoformat(timespec="seconds"))
    except Exception as e:  # a broken benchmark must never break /docs
        _bench.update(state="error", error=f"{type(e).__name__}: {e}"[:300])


def benchmarks() -> dict:
    with _bench_lock:
        if _bench["state"] == "not started":
            _bench["state"] = "running"
            threading.Thread(target=_run_benchmarks, name="docs-benchmarks", daemon=True).start()
    return dict(_bench)


# ---------- snapshot ----------

_cache: dict = {"at": 0.0, "data": None}


def snapshot(app) -> dict:
    if _cache["data"] is None or time.time() - _cache["at"] > 10:
        _cache["data"] = {"features": features(), "endpoints": endpoints(app), "knowledge": knowledge(),
                          "system": system(app)}
        _cache["at"] = time.time()
    return {**_cache["data"], "usage": usage(), "benchmarks": benchmarks(),
            "generated_at": datetime.now(timezone.utc).astimezone(BD).isoformat(timespec="seconds")}
