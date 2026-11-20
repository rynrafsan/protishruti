# Protishruti — context for AI coding assistants

## What this is
A prototype that checks what a broker promised a Bangladeshi migrant worker against their visa, contract and payslips, flags mismatches, explains them in plain Bangla, and saves a tamper-evident record. Competition: International AI Builders Congress 2026 (JusticeSphere AI → Legal Copilot).

## Non-negotiable design rules
- `app/rules.py` is the ONLY place that raises flags. LLMs extract and explain; they never decide.
- Never output or store passport/NID/phone numbers unmasked (`app/redact.py`).
- Never tell the user a job, agency or document is "safe" or "genuine". Always return `not_checked`.
- Synthetic SPECIMEN data only until `ALLOW_REAL_DATA=true` (after legal review + local image masking).
- Every flag must carry a `source` (document, law or reference table).

## Layout
- `app/schema.py` — Promise / Flag / CheckResult (pydantic). All inputs map to `Promise`.
- `app/rules.py` — R01–R12 rules + reference data loaders (`data/*.json`, agency CSV).
- `app/extract.py` — transcript → Promise (LLM or offline heuristic in mock mode).
- `app/docreader.py` — document image/JSON → Promise.
- `app/asr.py` — Bengali.AI regional Whisper (enable with ASR_ENABLED=true).
- `app/explain.py` — flags → Bangla text (LLM or template).
- `app/record.py` — SHA-256 hash-chained records + HTML view.
- `app/main.py` — FastAPI: `/api/check`, `/api/records/{id}`, `/health`; `app/whatsapp.py` — webhook.
- `app/docsite/` — live `/docs` (pitch deck + tech docs + live data) and `/docs/admin`; content in `data/docs/content.json`. Swagger is at `/api/docs`.
- `tools/synth/` — synthetic case generator + renderer; `tools/evaluate.py` — per-rule recall.

## Conventions
- Python 3.11+, type hints, pydantic v2, no global state except caches and the demo WhatsApp session dict.
- Add a test in `tests/` for every new rule; run `pytest -q` and `python tools/evaluate.py` before pushing.
- Prompts live in `app/prompts.py`; version changes are recorded in `PROMPTS.md`.
- Bangla text: normalise with `unicodedata.normalize("NFC", ...)` before matching.
