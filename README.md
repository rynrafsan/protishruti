<p align="center">
  <img src="frontend/brand/logo-light.svg#gh-light-mode-only" alt="প্রতিশ্রুতি Protishruti" height="72">
  <img src="frontend/brand/logo-dark.svg#gh-dark-mode-only" alt="প্রতিশ্রুতি Protishruti" height="72">
</p>

# Protishruti (প্রতিশ্রুতি) — build, develop and deploy guide

Protishruti checks what a broker promised a migrant worker against their visa, contract and payslips. It flags mismatches with fixed rules, explains them in plain Bangla, and saves a tamper-evident record.

> **Status: prototype.** Synthetic SPECIMEN data only. Legal information, not legal advice.

This repository already runs end to end in **mock mode** (no API keys, no GPU). You switch on real AI step by step: document reading, then speech, then WhatsApp.

---

## 0. How it works

```
voice note / text ─▶ speech-to-text ─┐
document photos   ─▶ document reader ─┼─▶ Promise fields ─▶ RULES ENGINE (flags) ─▶ Bangla explainer ─▶ result + Promise Record
payslips          ─▶ document reader ─┘                       ▲ cost caps, agency list, watchlist
```

- **Rules decide, AI explains.** `app/rules.py` is the only place that raises a flag.
- **Rights answers use RAG.** `app/rag.py` retrieves cited passages from `data/knowledge/` (see section 0.1).
- 12 rules: R01 job mismatch · R02 domestic-worker visa · R03 employer name · R04 salary · R05 fee above cap · R06 agency licence · R07 no contract · R08 risky corridor · R09 visa expiry · R10 underpaid · R11 large deductions · R12 late salary.

```
app/            FastAPI app (schema, rules, extract, docreader, asr, explain, record, whatsapp)
data/           reference data: cost caps, FX, agency list (sample), watchlist
data/knowledge/ RAG knowledge base: OEMA 2013, fee caps, complaints, helplines, agencies (each section cites a source URL)
frontend/       single-page upload UI (served at /)
frontend/brand/ logo (SVG), icons, favicon, social preview image, web manifest
frontend/docs/  the live /docs page, its admin panel and the "not available" page
app/docsite/    /docs backend: visibility + schedule, admin sign-in, drafts, versions, live data, GitHub sync
data/docs/      content.json: the committed /docs content (tools/docs_default.py writes the first version)
tools/synth/    synthetic case generator + renderer
tools/          evaluate.py (rule recall), asr_eval.py (WER per dialect), rag_eval.py, rag_contexts.py
tests/          pytest unit tests
CLAUDE.md       context file for AI coding assistants
PROMPTS.md      prompt library (for the submission form)
```

### 0.1 Rights Q&A (RAG)

```
question ─▶ redact (phone/passport/NID) ─▶ understand: Banglish → Bangla, everyday words and situations → legal terms,
                                            country + amount paid
   ├─ fee question? ─▶ government table (data/cost_caps.json): cap, average actually paid, over-payment worked out
   └─ otherwise ─▶ BM25 (keywords; the user's words weigh more than added synonyms)
                 ─▶ TF-IDF character 3–5-gram vectors (meaning-ish, spelling-tolerant)
                 ─▶ Reciprocal Rank Fusion ─▶ relevance gate (refuse if nothing really matches) ─▶ top 4 passages
                 ─▶ AI writes a cited answer (ANSWER_PROMPT_V2) ─▶ grounding check: every [n] exists and every
                    number is in the passages; fails, AI busy or no AI ─▶ best sentences word for word
```

- **Knowledge base:** 6 markdown files in `data/knowledge/` (28 passages): OEMA 2013, fee caps, complaints, helplines, agencies, safe migration. Every section ends with `সূত্র: <URL>`. Chunking follows the `##` sections, split only above 900 characters.
- **Contextual retrieval:** each passage is indexed with "document > section"; `python tools/rag_contexts.py` adds an AI-written context sentence per passage and saves `contexts.json` (commit it).
- **Answer modes:** `fact` (fee table, exact), `generated` (AI from passages, passed the grounding check), `extractive` (best sentences word for word), `no_match` (refuses and gives 16135). Each answer also returns confidence, call buttons (16135, 16699, 999, OEP), highlighted source sentences, follow-up questions and retrieval scores.
- **Where it is used:** `POST /api/ask` and `GET /api/ask/topics` (website "অধিকার নিয়ে প্রশ্ন করুন", with voice questions), WhatsApp messages starting with `প্রশ্ন` or `?`, every flag's `refs`, and the "এ নিয়ে প্রশ্ন করুন" link under each warning.
- **Settings:** `RAG_GENERATE=true` lets the AI write answers (Groq: about 500 tokens each; on the free tier's per-minute limit it falls back at once instead of waiting). `false` = offline sentences only.
- **Evaluation:** `python tools/rag_eval.py` (offline, no AI calls). 41 tuning questions in Bangla, Banglish and English: hit@3 100%, key fact in the answer 41/41, 5/5 off-topic refused. 16 held-out questions written after tuning, **first run**: hit@1 88%, hit@3 100%, MRR 0.94, key fact 12/16 (75%); the four misses were general gaps that are now fixed (16/16), so that set is no longer unseen.

### 0.2 Live docs (`/docs`)

`/docs` is a pitch deck, the technical documentation and a live view of the running system on one page, for judges and investors. The interactive API reference moved to `/api/docs`.

- **Pitch deck** (Problem → Vision, 12 sections, every figure with a source link) with a **Present** button that turns it into full-screen slides (arrow keys, Esc).
- **Technical documentation**: overview, feature matrix, architecture and data-flow diagrams (Mermaid), stack, API, data layer, AI layer, roadmap, performance, security, analytics, contributors, changelog.
- **Live panels**, read from the running app every 30 seconds: features switched on, endpoints (from OpenAPI), knowledge-base size, usage counts and response times since start, and the rule benchmark and RAG evaluation **re-run on the server** the first time `/docs` is opened after a start (offline, no AI calls, about a second).
- Search (`/`), section links, Markdown export (`/docs/export.md`), print/PDF, share link.

**Admin panel: `/docs/admin`.** Set the passwords in the environment (12+ characters; never commit them):

| Variable | Default | What it does |
|---|---|---|
| `DOCS_ADMIN_PASSWORD` | empty (admin off) | Admin: edit, save drafts, publish, turn /docs on or off, set the window, upload team photos |
| `DOCS_SUPERADMIN_PASSWORD` | empty | Super Admin: also restore old versions, reset content or settings, read the activity log |
| `DOCS_SECRET` | random per start | Signs admin sessions; set it so sign-ins survive restarts |
| `DOCS_PUBLIC` | `true` | Master switch; `false` shows a "not available" page (HTTP 403) |
| `DOCS_SCHEDULE` | `true` | Use the window below |
| `DOCS_OPEN_FROM` / `DOCS_OPEN_UNTIL` | `2026-11-20T00:00` / `2026-12-31T23:59` | Window in Bangladesh time (GMT+6); the end minute is included |
| `DOCS_GITHUB_REPO` / `DOCS_GITHUB_TOKEN` | empty | Optional: each publish commits `data/docs/content.json`, each visibility change `data/docs/settings.json` |
| `DOCS_DATA_DIR` | `data/runtime/docs` | Where drafts, versions and the activity log are kept |

The order of precedence for visibility: environment → `data/docs/settings.json` (committed) → changes made in the admin panel on this server. Signed-in admins can always open `/docs`, with a ribbon saying whether the public can.

**On Render's free plan the disk is wiped on every restart** (and the free server restarts after 15 idle minutes). Admin-panel changes therefore last only until the next restart unless you make them permanent: set the `DOCS_*` visibility variables in Render, and either download `content.json` from the admin panel and commit it to `data/docs/`, or set `DOCS_GITHUB_REPO` (e.g. `rynrafsan/protishruti`) and `DOCS_GITHUB_TOKEN` (a fine-grained token for this one repository with *Contents: read and write*) so publishing commits for you; Render then redeploys with the new content.

`python tools/docs_default.py` rewrites `data/docs/content.json` from the script (it overwrites edits; prefer the admin panel). Tests: `tests/test_docs.py`.

---

## Phase 1 — Run it locally (30 minutes)

**You need:** Python 3.11+, Git, and VS Code (or any editor).

```bash
git clone <your-repo-url> protishruti && cd protishruti
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # leave LLM_PROVIDER=mock for now
pytest -q                          # expect: all tests pass
uvicorn app.main:app --reload
```

Open http://localhost:8000 and paste a test promise:

```
সৌদিতে ফ্যাক্টরির কাজ, বেতন ৩৫ হাজার টাকা। আমি মোট ৪ লাখ টাকা দিয়েছি। লাইসেন্স RL-9001।
```

You should see R05 (fee above the Saudi cap) and R07 (no written contract). Click the record link to see the hashed Promise Record. The live pitch deck and technical docs are at http://localhost:8000/docs (section 0.2); the interactive API reference is at http://localhost:8000/api/docs.

**First commit:** create a GitHub repository (private until you are ready), then push.

---

## Phase 2 — Build the test data (day 1)

```bash
python tools/synth/generate.py --n 200 --out data/synthetic   # 200 cases, one planted mismatch each
python tools/evaluate.py --dir data/synthetic                  # rule recall on ground-truth fields
python tools/evaluate.py --dir data/synthetic --extract        # transcript -> extractor -> rules
```

Each case has `transcript_bn.txt`, `promise.json`, `visa.json`, `contract.json`, `visa.html` (SPECIMEN) and `label.json`. You can upload the `.json` files in the UI to test the pipeline without a vision model.

Render the visas to images with camera noise, to test the document reader:

```bash
pip install playwright opencv-python-headless && playwright install chromium
python tools/synth/render.py --dir data/synthetic --noise
```

**Important:** the synthetic transcripts follow one template, so the high recall here proves the rules work. It does **not** prove real-world accuracy. Real dialect recordings (Phase 4) are the honest test.

### Real datasets for later phases

| Need | Source |
|---|---|
| Dialect speech | Ben-10: https://huggingface.co/datasets/bengaliAI/Ben-10 · code: https://github.com/BengaliAI/reg-speech-aacl |
| Bangla speech | SUBAK.KO: https://huggingface.co/datasets/SUST-CSE-Speech/SUBAK.KO · OpenSLR 53: https://openslr.org/53/ |
| Dialect text | Vashantor: https://data.mendeley.com/datasets/bj5jgk878b/2 |
| Arabic documents (benchmark) | KITAB-Bench: https://mbzuai-oryx.github.io/KITAB-Bench |
| Law | OEMA 2013 (Bangla): http://bdlaws.minlaw.gov.bd/act-1131.html · Saudi Labour Law (EN): https://www.wipo.int/wipolex/edocs/lexdocs/laws/en/sa/sa055en.pdf · Malaysia Employment Act: https://jtksm.mohr.gov.my/sites/default/files/2023-11/Akta%20Kerja%201955%20(Akta%20265).pdf · ILO fair recruitment: https://www.ilo.org/node/180231 |
| Agency registry | Overseas Employment Platform: https://www.oep.gov.bd · https://raims.oep.gov.bd |
| Statistics | BMET open data: https://data.gov.bd/bn/dataset/overseas-employment-data · KNOMAD-ILO: https://microdata.worldbank.org/catalog/2944 |

**Agency list:** replace `data/agencies_sample.csv` (fictional) with a snapshot from the official registry. Keep the columns `license_no,name,status,valid_until`, and set `AGENCY_CSV`. Re-check the cost caps in `data/cost_caps.json` against the latest ministry circular.

---

## Phase 3 — Turn on real AI for documents and extraction (day 2)

1. Get a free Groq API key at https://console.groq.com/keys (no card needed). Gemini and Claude also work.
2. Edit `.env`:
   ```
   LLM_PROVIDER=groq            # or gemini / anthropic
   OPENAI_API_KEY=...           # your Groq key; check the vision model name at console.groq.com/docs/vision
   ```
   Test it with `python tools/llm_ping.py`.
3. Restart the server and upload a rendered `visa_photo.png` from `data/synthetic/case_*/`.

**Data safety rules (keep these until legal review):**
- Only SPECIMEN or synthetic documents go to external APIs. Free tiers may use your inputs to improve the provider's products.
- `ALLOW_REAL_DATA=false` stays false.
- Text is masked by `app/redact.py`. Image masking (blurring ID numbers on photos with a local OCR model before any API call) is still to be built. It must be done before real documents are allowed.

**Open-model option:** serve `Qwen/Qwen3-VL-8B-Instruct` with vLLM or Ollama and point `OPENAI_BASE_URL` at it (the `openai` provider speaks any OpenAI-compatible API). Benchmark Gemini, Claude and Qwen on your rendered synthetic set, plus a KITAB-Bench subset, and keep the best.

---

## Phase 4 — Dialect speech-to-text (days 2–5, your specialty)

```bash
pip install -r requirements-asr.txt jiwer      # also install ffmpeg
ASR_ENABLED=true uvicorn app.main:app --reload
```

The default model is `bengaliAI/tugstugi_bengaliai-regional-asr_whisper-medium` (Apache-2.0), already fine-tuned on 10 dialects.

1. **Collect a test set remotely.** About 30 classmates from Cumilla, Brahmanbaria, Chandpur, Noakhali, Sylhet and Chattogram record the transcripts from `data/synthetic/*/transcript_bn.txt` **in their own dialect** on WhatsApp. Get written consent first.
2. **Measure:** write `data/voice_test.csv` with the columns `path,reference,dialect`, then run `python tools/asr_eval.py --csv data/voice_test.csv`. Report WER for every dialect, including the weak ones.
3. **Fine-tune (Kaggle GPU, about 30 free hours a week):** start from the regional model and add Ben-10 plus your recordings. Use the Hugging Face `Seq2SeqTrainer` Whisper recipe with fp16, batch size 8, learning rate 1e-5, and 2–4k steps. Keep a held-out set of speakers. Push the result to the Hub and set `ASR_MODEL`.
4. **Read-back safety:** the app always shows the extracted promise for the worker to confirm. Never put an unconfirmed transcription into a record.

---

## Phase 5 — Deploy (day 3 onward)

### Option A: Render (simplest, free tier)
1. Push to GitHub.
2. Render → **New → Blueprint** → choose the repository (it reads `render.yaml`).
3. Add `OPENAI_API_KEY` (your Groq key) in the dashboard; `LLM_PROVIDER` is already `groq`.
4. Optional, for `/docs/admin`: add `DOCS_ADMIN_PASSWORD`, `DOCS_SUPERADMIN_PASSWORD` and `DOCS_SECRET` (see section 0.2).
5. Open `https://<app>.onrender.com/health`, then `/docs`.

Free-tier caveats: the service sleeps when idle (the first request is slow), and the disk is temporary, so records disappear on redeploy. Use a database for anything you need to keep.

### Option B: Hugging Face Spaces (good if you need a GPU for speech)
Create a **Docker** Space, push this repository, and change the last line of the Dockerfile to listen on port 7860. Add secrets in the Space settings. Paid GPU hardware is needed for ASR at a usable speed.

### Option C: Any VPS or local machine with Docker
```bash
docker build -t protishruti .
docker run -p 8000:8000 --env-file .env protishruti
```

**Speech-to-text on free CPU hosting is slow.** For the demo, either run speech on a GPU Space or record the voice part on a laptop with a GPU, and keep the deployed demo text-and-document based.

---

## Phase 6 — WhatsApp (after the web demo works)

1. Go to https://developers.facebook.com → create an app → add the **WhatsApp** product. A free test number is created, and it can message up to **5 verified phone numbers** (your team's phones).
2. Set `WA_VERIFY_TOKEN` (any secret string you choose), `WA_ACCESS_TOKEN`, `WA_PHONE_NUMBER_ID (and WA_DISPLAY_NUMBER to show the number on the website)` and `PUBLIC_BASE_URL` in the environment.
3. In Meta's WhatsApp configuration, set the webhook URL to `https://<your-domain>/whatsapp/webhook` with the same verify token, and subscribe to `messages`. The webhook must be public HTTPS. For local testing use `ngrok http 8000` or Cloudflare Tunnel.
4. Test from a verified phone: send `help`, then a text promise, then a document photo, then `check`.

The webhook replies at once and does the work in a background task, because Meta expects a fast response. Sessions are in memory; move them to Redis or Postgres before real use. Going public needs a real number and Meta business verification.

---

## Phase 7 — From prototype to pilot (after the Congress)

- [ ] **Database:** Postgres for sessions and records; object storage for attachments; keep the hash chain.
- [ ] **Legal knowledge search:** load laws into Postgres + pgvector (BGE-M3 embeddings), and cite sections in explanations.
- [ ] **Queue:** Redis + RQ/Celery workers for speech and document jobs.
- [ ] **Image masking:** local OCR to blur ID numbers before any API call; then legal review → `ALLOW_REAL_DATA=true`.
- [ ] **Hosting:** sensitive data on servers in Bangladesh or the region (Personal Data Protection Ordinance 2025: confirm current duties with a lawyer).
- [ ] **Mentor console** with login, audit log and least-privilege access.
- [ ] **Licences:** MMS-TTS Bengali is non-commercial (CC-BY-NC-4.0); replace it before any commercial use.
- [ ] **Pilot:** one NGO partner, 100–300 users, DIU ethics approval, written consent, a human reviews every flag.
- [ ] **Monitoring:** error tracking, per-rule flag rates, false "all clear" reviews.

---

## Suggested plan to 26 December

| Week | Goal |
|---|---|
| 17–23 Nov | This repo running locally and deployed; 200 synthetic cases; preliminary submission |
| 24–30 Nov | Real document reading (LLM); dialect test set recorded; first WER numbers |
| 1–7 Dec | Fine-tuned ASR; WhatsApp test number working; Bangla explainer polished |
| 8–14 Dec | Payslip stage, complaint draft, user tests with 15–20 people (remote) |
| 15–21 Dec | Full benchmark, fixes, metrics slide, pitch deck |
| 22–25 Dec | Code freeze, rehearsal, backup demo video |

## Metrics to report
Recall per rule (`tools/evaluate.py`), retrieval hit@3 and MRR (`tools/rag_eval.py`), WER per dialect (`tools/asr_eval.py`), field-extraction accuracy on rendered documents, the false "all clear" rate, and time from upload to answer.

## Troubleshooting
- `ASR is disabled` → set `ASR_ENABLED=true` and install `requirements-asr.txt` and ffmpeg.
- `Model did not return JSON` → check the API key and model name; lower image size; retry.
- WhatsApp webhook `403` → the verify token in Meta must equal `WA_VERIFY_TOKEN`.
- Recipient not allowed (WhatsApp) → add the phone to the test number's allowed list.
