"""Writes data/docs/content.json: the default content of the live /docs page.

python tools/docs_default.py

After that, edit in the admin panel (/docs/admin). This script is the starting point only; running it
again overwrites data/docs/content.json (the admin panel's "Download content.json" is the way to save edits).
Every number below carries its source link. Keep it that way.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "docs" / "content.json"

SRC = {
    "rmmru_2025": "https://thefinancialexpress.com.bd/national/bangladeshs-overseas-labour-migration-up-12pc-in-2025-rmmru",
    "bss_2025": "https://b.bssnews.net/news/348159",
    "remit": "https://www.tbsnews.net/economy/remittance-inflow-hits-record-30b-fy25-1176781",
    "remit_gdp": "https://www.thedailystar.net/business/news/remittance-share-gdp-imports-rises-7-year-high-3993151",
    "decade": "https://asianews.network/?p=292571",
    "okup": "https://www.tbsnews.net/bangladesh/migration/false-promises-abroad-no-justice-home-new-study-sheds-light-migrants-perils",
    "rmmru_return": "https://www.tbsnews.net/node/744970",
    "bbs_cost": "https://www.thedailystar.net/node/2959876",
    "sa_cap": "https://www.thedailystar.net/frontpage/saudi-job-tk-165-lakh-1278076",
    "oema": "https://www.thedailystar.net/node/3391481",
    "oep": "https://oep.gov.bd/",
    "probash": "https://www.dhakatribune.com/bangladesh/293573/govt-launches-probash-bondhu-hotline-service-for",
    "render_free": "https://render.com/docs/free",
}


def a(key, text="source"):
    return f'<a href="{SRC[key]}">{text}</a>'


def sec(id, group, title, body, kicker="", **kw):
    return {"id": id, "group": group, "type": kw.pop("type", "richtext"), "title": title, "kicker": kicker,
            "body": body, "visible": True, "live": kw.pop("live", ""), "figures": kw.pop("figures", []), **kw}


def fig(value, label, source=""):
    return {"value": value, "label": label, "source": SRC.get(source, source)}


ARCH = """flowchart TB
  web["Web app<br>one page, no framework"]
  wa["WhatsApp<br>Meta Cloud API"]
  docs["/docs<br>this page"]
  main["main.py<br>/api/check · /api/ask · /api/transcribe"]
  hook["whatsapp.py<br>/whatsapp/webhook"]
  site["docsite<br>/docs · /docs/admin"]
  listen["Listen and read<br>asr.py · redact.py · extract.py · docreader.py"]
  decide{{"Decide<br>rules.py: R01–R12"}}
  explain["Explain and cite<br>legal.py · rag.py · explain.py"]
  rec["Record<br>record.py: SHA-256 chain"]
  groq[["Groq API<br>qwen3.8-27b · whisper-large-v3"]]
  ref[("Fee caps, FX,<br>agency list, watchlist")]
  kb[("Knowledge base<br>28 sourced passages")]
  recs[("records/<br>chain.json")]
  dd[("data/docs<br>content, settings")]
  web --> main
  wa --> hook
  docs --> site
  main --> listen
  hook --> listen
  listen --> decide --> explain --> rec
  main -- "rights questions" --> explain
  decide --> ref
  explain --> kb
  rec --> recs
  site --> dd
  listen -. "AI" .-> groq
  explain -. "AI" .-> groq"""

FLOW = """flowchart TD
  v["Voice note or typed promise"] --> s["Speech to text<br>Whisper large-v3, Bangla"]
  s --> c["Worker reads and corrects the text"]
  c --> m["Mask passport, NID and phone numbers"]
  m --> x["Extract promise fields<br>AI, or offline extractor"]
  p["Photos: visa, contract, payslips"] --> r["Read documents<br>vision model, JSON schema"]
  x --> g{"12 fixed rules"}
  r --> g
  t[("Fee caps, FX, agency list,<br>watchlist")] --> g
  g --> f["Warnings, each with its source,<br>law section, next step and cited passages"]
  f --> e["Plain-Bangla explanation<br>on screen or WhatsApp"]
  e --> k[("Promise Record<br>SHA-256 hash chain")]
  e --> act["Worker acts: does not pay,<br>calls 16135, complains to BMET"]
  act -. "feedback" .-> fb["Corrections and new questions<br>become test cases and passages"]"""

sections = [
    # ------------------------------------------------------------------ pitch deck
    sec("problem", "pitch", "Problem",
        kicker="A broker's spoken promise can cost a worker lakhs of taka, and nothing on paper backs it.",
        figures=[fig("৳4.36 lakh", "average a worker actually paid to go to Saudi Arabia (BBS survey 2015–18). The government cap today is ৳1.65 lakh.", "bbs_cost"),
                 fig("75%", "of 114 workers who took a complaint to BMET said they got no job contract before leaving (OKUP, 2023–24)", "okup"),
                 fig("20.1%", "of early returnees in an RMMRU study did not get the job and salary they were promised", "rmmru_return")],
        body="""<p>Most Bangladeshi workers find an overseas job through a broker (<em>dalal</em>). The deal is spoken: "factory job in Saudi, 40,000 taka a month, pay 4 lakh". The visa, the contract and the demand letter are in Arabic or English, so the worker cannot check them against what was said.</p>
<p>The mismatch shows up after the money is paid and the worker has landed: a different job, a lower salary, a domestic-worker visa, no contract at all. By then there is nothing to show for the promise.</p>
<p>The law is on the worker's side. Taking money with a false promise is a crime under section 31 of the Overseas Employment and Migrants Act 2013 (""" + a("oema") + """), and the government sets a maximum migration cost for each main destination. Most workers never learn either.</p>"""),
    sec("solution", "pitch", "Solution",
        kicker="Say what the broker promised. Photograph the papers. See every mismatch, the law, and what to do next.",
        body="""<ol>
<li><strong>Tell it the promise.</strong> Record a voice note in Bangla (dialects welcome) or type it. The worker reads the transcript and fixes it before anything is checked.</li>
<li><strong>Add the papers.</strong> Photos of the visa, contract, demand letter or payslips, in Arabic, English, Malay or Bangla.</li>
<li><strong>Twelve fixed rules compare them:</strong> job, visa type, employer, salary, fee against the government cap, agency licence, written contract, risky corridor, visa expiry, and after arrival, salary paid, deductions and late pay.</li>
<li><strong>Every warning comes with its source:</strong> what was promised, what the paper says, the section of the law, the next step and the helpline to call.</li>
<li><strong>A Promise Record</strong>, hash-chained so it cannot be changed quietly, to take to BMET, the district office or a free legal-aid lawyer.</li>
</ol>
<p>The same checks run on WhatsApp, and a rights Q&amp;A answers questions about fees, complaints and the law with citations.</p>
<p><strong>Rules decide, AI explains.</strong> The AI listens, reads and writes plain Bangla; only written rules raise a warning. Protishruti never tells a worker a job is safe or genuine. It says what it checked and what it could not.</p>"""),
    sec("why-now", "pitch", "Why now",
        kicker="More workers are leaving than ever, and the tools to read their papers now cost nothing.",
        figures=[fig("1.13 million", "Bangladeshis went abroad for work in 2025, up 12% on 2024 (RMMRU, from BMET data)", "rmmru_2025"),
                 fig("$30 billion", "record remittances in FY2024–25, 6.57% of GDP (Bangladesh Bank)", "remit_gdp")],
        body="""<ul>
<li><strong>Volume and concentration.</strong> 752,715 of 2025's workers went to one country, Saudi Arabia (""" + a("bss_2025", "BMET via BSS") + """). One fee cap and one visa format cover most of the risk.</li>
<li><strong>AI that reads Bangla speech and Arabic paper is now free to try.</strong> Open speech and vision models served on free tiers (Whisper large-v3, Qwen on Groq) make a check cost the worker nothing.</li>
<li><strong>Official rails exist to route people to.</strong> Agency licences are public on the Overseas Employment Platform (""" + a("oep", "oep.gov.bd") + """) and the Probash Bondhu call centre (16135) is free and open all day (""" + a("probash") + """). Protishruti sends workers there with evidence instead of replacing them.</li>
</ul>"""),
    sec("demo", "pitch", "Product demo", live="demo",
        kicker="Try a check in under two minutes. Everything runs on fictional SPECIMEN data.",
        body="""<ol>
<li>Open the app and go to <strong>যাচাই করুন</strong> (Check).</li>
<li>Type this promise: <code>দালাল বলেছে সৌদিতে ফ্যাক্টরির কাজ, বেতন ৪০ হাজার টাকা। আমি ৪ লাখ টাকা দিয়েছি। কোনো চুক্তিপত্র দেয় নাই।</code></li>
<li>Press check. Expect three warnings: <strong>R05</strong> fee above the Saudi cap of ৳1,65,000, <strong>R06</strong> no agency licence number given, <strong>R07</strong> no written contract. Each shows the law and the next step.</li>
<li>Open the Promise Record link to see the hashed record.</li>
<li>In <strong>অধিকার নিয়ে প্রশ্ন করুন</strong>, ask <code>কাতার যেতে ৪ লাখ টাকা দিয়েছি, বেশি হয়েছে?</code> to see the over-payment worked out from the government table, with sources.</li>
</ol>""", video_url=""),
    sec("market", "pitch", "Market opportunity",
        kicker="Every year about a million people make a decision worth several lakh taka on the word of a broker.",
        figures=[fig("1.13 million", "workers left in 2025", "rmmru_2025"),
                 fig("8.6 million", "left for overseas jobs between FY2015 and FY2025 (BMET)", "decade"),
                 fig("৳2.71 lakh", "gap per Saudi-bound worker between the average paid (৳4.36 lakh) and today's cap (৳1.65 lakh)", "bbs_cost")],
        body="""<p><strong>Beachhead:</strong> workers preparing to go to Saudi Arabia, two thirds of 2025's departures, and the families who pay for the trip. One corridor, one fee cap, one visa format.</p>
<p><strong>Next:</strong> workers already abroad (payslip checks: underpaid, cut or late salary), then the other main corridors (Qatar, Kuwait, Singapore, Malaysia when it reopens). The rules-plus-sources design carries over to other countries that send workers through brokers.</p>
<p><strong>Who pays:</strong> not the worker. See the business model.</p>
<p class="note">The ৳2.71 lakh gap compares a 2015–18 survey average with today's cap, so treat it as an order of magnitude, not a measurement.</p>"""),
    sec("business-model", "pitch", "Business model",
        kicker="Free for workers, always. Paid for by the institutions whose job is to protect them.",
        body="""<table><thead><tr><th>Who</th><th>What they get</th><th>How it is paid</th></tr></thead><tbody>
<tr><td>Workers and families</td><td>Checks, rights answers, Promise Records, on the web and WhatsApp</td><td>Free. No account, no ads.</td></tr>
<tr><td>Migrant-rights NGOs and training centres</td><td>A caseworker version: checks run with the worker, records ready for a complaint</td><td>Licence or grant-funded deployment</td></tr>
<tr><td>Government help desks (Probash Bondhu, BMET, district offices)</td><td>Structured, hash-verified case files instead of a phone description of papers</td><td>Service contract (B2G)</td></tr>
<tr><td>Policy and research partners</td><td>Corridor-level statistics on mismatches and over-payment, aggregated and anonymous</td><td>Only with consent and after legal review</td></tr>
</tbody></table>
<p>These are hypotheses. No customer has been asked yet; the first test is the pilot in the go-to-market plan. Running costs today are zero: free AI tiers and a free server.</p>"""),
    sec("traction", "pitch", "Traction", live="traction",
        kicker="Pre-launch prototype. What we can show is that it works, and the numbers below are measured on this server.",
        body="""<ul>
<li>Working end to end: voice, documents, 12 rules, legal next steps, rights Q&amp;A, records, WhatsApp webhook. Deployed on Render.</li>
<li>Preliminary submission to the International AI Builders Congress 2026 (CloudCamp), 20 November 2026.</li>
<li>No real users yet, on purpose: the app runs on fictional SPECIMEN data until a legal team has reviewed every rule and passage.</li>
</ul>"""),
    sec("competition", "pitch", "Competition",
        kicker="Good help exists. None of it checks the broker's words against the worker's own papers before the money is paid.",
        body="""<table><thead><tr><th>Alternative</th><th>Strength</th><th>What it leaves to the worker</th></tr></thead><tbody>
<tr><td>Asking the broker or agency</td><td>Quick and local</td><td>The person checking is the person selling</td></tr>
<tr><td>Probash Bondhu call centre (16135)</td><td>Official, free, open all day</td><td>Describing papers they may not be able to read, over the phone</td></tr>
<tr><td>Overseas Employment Platform (oep.gov.bd)</td><td>Official agency licence lookup</td><td>Checks the agency, not the job, salary or fee that was promised</td></tr>
<tr><td>BMET complaint and arbitration</td><td>Can return money</td><td>Comes after the loss, takes months, needs evidence</td></tr>
<tr><td>Migrant-rights NGOs</td><td>Expert and trusted</td><td>Limited staff and reach</td></tr>
<tr><td>General AI chatbots</td><td>Answer anything</td><td>Can guess, have no fee table, may call a job "fine"</td></tr>
</tbody></table>
<p>Protishruti works before payment, on the worker's phone, in spoken Bangla, against the actual documents, and hands the worker over to the official channels above with evidence.</p>"""),
    sec("advantage", "pitch", "Unique advantage",
        kicker="Auditable by design: every warning can be traced to a rule and a source.",
        body="""<ul>
<li><strong>Rules decide, AI explains.</strong> A hallucination cannot become a verdict. The 12 rules are plain Python with tests.</li>
<li><strong>Sourced knowledge.</strong> Every passage in the knowledge base and every fee cap links to where it came from. Answers that cite a missing passage or a number not in the sources are thrown away automatically.</li>
<li><strong>Built for the worker's phone.</strong> Bangla voice first, Banglish questions understood, WhatsApp channel, one light page.</li>
<li><strong>Evidence, not just advice.</strong> The Promise Record is hash-chained; editing an old record breaks every later hash.</li>
<li><strong>Private by default.</strong> No accounts. Passport, NID and phone numbers are masked before storage or any AI call.</li>
<li><strong>Measured.</strong> A synthetic case generator, a per-rule benchmark and a RAG evaluation set run on every change, and live on this page.</li>
</ul>"""),
    sec("gtm", "pitch", "Go-to-market",
        kicker="Meet workers where the decision is made: districts that send the most people, and the WhatsApp they already use.",
        body="""<ol>
<li><strong>Legal review (before any real data).</strong> A legal team checks every rule, passage and fee figure. <code>ALLOW_REAL_DATA</code> stays off until then.</li>
<li><strong>Pilot with one partner.</strong> A migrant-rights NGO or a training centre in a top-sending district (Cumilla and Brahmanbaria led in 2025, """ + a("rmmru_2025", "RMMRU") + """). Caseworkers run checks with workers; we measure what the warnings change.</li>
<li><strong>WhatsApp number at the decision points:</strong> pre-departure orientation, union digital centres, migrant community groups online.</li>
<li><strong>Institutional deals</strong> once the pilot shows workers paying less or refusing bad offers.</li>
</ol>
<p>Pilot metrics: checks completed, share with a critical warning, warnings acted on (did not pay, asked for a contract, complained), and over-payment avoided.</p>"""),
    sec("team", "pitch", "Team", type="team", team_name="Team Singularity",
        kicker="Daffodil International University, Dhaka.",
        body="",
        members=[{"id": "raiyan", "name": "Raiyan Jahan", "role": "Team lead", "email": "", "photo": "",
                  "bio": "Final-year CSE student, Daffodil International University"}]),
    sec("vision", "pitch", "Vision",
        kicker="No worker should pay for a promise the papers do not keep.",
        body="""<p>A check before paying becomes as normal as asking for a receipt. Every Bangladeshi worker can hear, in their own dialect, what their papers really say and what the law gives them, and can walk into an office with evidence instead of a story.</p>
<p>The rules and the knowledge base stay open, so lawyers, NGOs and the government can audit exactly why Protishruti said what it said.</p>"""),

    # ------------------------------------------------------------------ technical documentation
    sec("overview", "tech", "Product overview",
        kicker="What it does, who it is for, and the jobs it covers.",
        body="""<h3>What it does</h3>
<p>Protishruti turns a spoken job offer into structured fields, reads the worker's documents into the same fields, compares them with 12 fixed rules and reference tables, and returns each mismatch with the law, a next step and cited sources, in plain Bangla. It also answers rights questions from a sourced knowledge base and keeps a tamper-evident record.</p>
<h3>Target users</h3>
<ul>
<li><strong>Primary:</strong> people about to migrate for work and their families. Often limited reading, Bangla speakers, on a phone.</li>
<li><strong>Secondary:</strong> workers already abroad with salary problems; caseworkers at NGOs and help desks who check papers with them.</li>
</ul>
<h3>Core use cases</h3>
<table><thead><tr><th>Use case</th><th>Rules / feature</th></tr></thead><tbody>
<tr><td>"Is this the job I was promised?"</td><td>R01 job, R02 visa type, R03 employer, R04 salary</td></tr>
<tr><td>"Did I pay too much?"</td><td>R05 fee cap, fee calculator, rights Q&amp;A</td></tr>
<tr><td>"Is the agency real?"</td><td>R06 licence, link to oep.gov.bd</td></tr>
<tr><td>"Do I have what I need before I fly?"</td><td>R07 contract, R08 risky corridor, R09 visa expiry</td></tr>
<tr><td>"I'm abroad and not paid properly"</td><td>R10 underpaid, R11 deductions, R12 late salary</td></tr>
<tr><td>"Where do I complain? What does the law say?"</td><td>Rights Q&amp;A with citations, helplines</td></tr>
<tr><td>"How do I prove it later?"</td><td>Promise Record (hash chain)</td></tr>
</tbody></table>"""),
    sec("features", "tech", "Feature matrix", live="features",
        kicker="Read from the running app: if a feature is switched off on this server, it shows here.",
        body="<p>Status: <strong>live</strong> works with AI on this server; <strong>fallback</strong> works without AI (offline method); <strong>pilot</strong> built but not connected here; <strong>off</strong> switched off by configuration.</p>",
        planned=[{"name": "Legal team review of every rule, passage and fee figure", "status": "upcoming", "note": "After the preliminary round; required before real data"},
                 {"name": "WhatsApp webhook signature check (X-Hub-Signature-256)", "status": "upcoming", "note": "Reject requests that did not come from Meta"},
                 {"name": "Rate limits on public endpoints", "status": "upcoming", "note": "Protect the free AI quota from abuse"},
                 {"name": "Dialect voice tests with volunteers", "status": "upcoming", "note": "tools/asr_eval.py reports word error rate per dialect"},
                 {"name": "Mask ID numbers on document images before any AI call", "status": "planned", "note": "Local OCR finds and blurs passport and NID numbers"},
                 {"name": "Official agency licence data", "status": "planned", "note": "Replace the sample list with data from oep.gov.bd"},
                 {"name": "Database for WhatsApp sessions and records", "status": "planned", "note": "Postgres instead of memory and files"},
                 {"name": "Trusted timestamps on Promise Records", "status": "research", "note": "RFC 3161 or OpenTimestamps proof per record"}]),
    sec("architecture", "tech", "Architecture", type="diagram", mermaid=ARCH,
        kicker="UI → API → services → data. One FastAPI app, no database, AI behind one switchable client.",
        caption="Solid arrows are calls inside the app; dotted arrows go to the AI provider. Every AI step has an offline fallback.",
        body="""<ul>
<li><strong>One process.</strong> FastAPI serves the page, the API, the WhatsApp webhook and this documentation.</li>
<li><strong>One AI client</strong> (<code>app/llm.py</code>) for Groq, any OpenAI-compatible API, Gemini or Claude, with timeouts, a cooldown after outages and a fail-fast mode on rate limits.</li>
<li><strong>Files instead of a database</strong> for the prototype: reference data and the knowledge base are versioned in git; records are JSON files chained by hash.</li>
</ul>"""),
    sec("data-flow", "tech", "Data flow", type="diagram", mermaid=FLOW,
        kicker="Input → processing → AI → output → feedback.",
        caption="The worker corrects the transcript before the check, so a speech-to-text mistake cannot become a false warning.",
        body=""),
    sec("stack", "tech", "Technology stack", live="stack",
        kicker="Small, boring and free to run.",
        body="""<table><thead><tr><th>Layer</th><th>Choice</th><th>Why</th></tr></thead><tbody>
<tr><td>Frontend</td><td>One HTML page, vanilla JavaScript, no build step; Tiro Bangla and Hind Siliguri fonts</td><td>Loads fast on cheap phones; nothing to compile</td></tr>
<tr><td>Backend</td><td>Python 3.12, FastAPI, Pydantic v2, httpx, Uvicorn</td><td>Typed schemas for every promise and warning</td></tr>
<tr><td>AI</td><td>Groq API: <code>qwen/qwen3.8-27b</code> (reading, extraction, answers), <code>whisper-large-v3</code> (speech)</td><td>Free tier, fast; provider can be switched in one setting</td></tr>
<tr><td>Retrieval</td><td>BM25 + TF-IDF character n-gram vectors (NumPy), Reciprocal Rank Fusion</td><td>No vector database or embedding API needed for 28 passages</td></tr>
<tr><td>Storage</td><td>JSON and Markdown files; SHA-256 hash-chained records</td><td>Versioned in git, nothing to administer</td></tr>
<tr><td>Images</td><td>Pillow</td><td>Shrinks phone photos before the AI call; team photos on this page</td></tr>
<tr><td>Messaging</td><td>WhatsApp Cloud API (Meta)</td><td>Where workers already are</td></tr>
<tr><td>Hosting</td><td>Docker (with ffmpeg) on Render's free plan</td><td>$0, deploys on every push</td></tr>
<tr><td>Quality</td><td>pytest, synthetic case generator, RAG evaluation set</td><td>Every change is measured</td></tr>
<tr><td>This page</td><td>FastAPI routes, vanilla JavaScript, Mermaid for diagrams</td><td>Same stack, no extra service</td></tr>
</tbody></table>"""),
    sec("api", "tech", "API documentation", live="api",
        kicker="The endpoint list below is generated from the running app. The interactive reference is at /api/docs.",
        body="""<h3>APIs we call</h3>
<table><thead><tr><th>API</th><th>Used for</th><th>Auth</th></tr></thead><tbody>
<tr><td>Groq chat completions (OpenAI-compatible)</td><td>Reading document photos (vision, JSON mode), reading transcripts, rights answers</td><td>API key in an environment variable</td></tr>
<tr><td>Groq audio transcriptions</td><td>Whisper large-v3 speech to text, Bangla</td><td>Same key</td></tr>
<tr><td>Meta WhatsApp Cloud API (Graph v22.0)</td><td>Receiving messages and media, sending results</td><td>Access token + phone number ID</td></tr>
<tr><td>Optional: Google Gemini, Anthropic Claude</td><td>Alternative AI providers</td><td>API key</td></tr>
</tbody></table>
<h3>Auth model</h3>
<ul>
<li>Worker-facing endpoints are public: workers never sign up, so there is no account to steal. Identity numbers are masked before storage.</li>
<li>Records are addressed by a random 12-character ID.</li>
<li>The WhatsApp webhook is registered with a verify token.</li>
<li>The admin endpoints of this page need a signed session cookie and a CSRF header (see Security). They are not listed below.</li>
</ul>"""),
    sec("data-layer", "tech", "Data layer", live="data",
        kicker="Where every fact comes from, how it is parsed, where it is kept, and what is never kept.",
        body="""<h3>Sources</h3>
<table><thead><tr><th>File</th><th>What</th><th>Origin</th></tr></thead><tbody>
<tr><td><code>data/knowledge/*.md</code></td><td>Rights knowledge base: OEMA 2013, fees, complaints, helplines, agencies, safe migration</td><td>Compiled from news and official pages; every section ends with its source URL</td></tr>
<tr><td><code>data/cost_caps.json</code></td><td>Government maximum migration cost per country, average actually paid</td><td>News reports of official circulars; BBS cost-of-migration survey</td></tr>
<tr><td><code>data/agencies_sample.csv</code></td><td>Agency licence list</td><td><strong>Sample, fictional.</strong> Workers are sent to oep.gov.bd for the real check</td></tr>
<tr><td><code>data/watchlist.json</code></td><td>Corridors with frequent fraud reports</td><td>News reports</td></tr>
<tr><td><code>data/fx_rates.json</code></td><td>Currency to taka, for salary comparison</td><td>Approximate rates</td></tr>
<tr><td><code>tools/synth/</code></td><td>Synthetic cases with one planted mismatch each</td><td>Generated; fictional names, SPECIMEN watermark</td></tr>
</tbody></table>
<h3>Parsing</h3>
<ul>
<li><strong>Documents:</strong> a vision model returns JSON in the <code>Promise</code> schema, quoting the original text for every field. Unreadable fields are listed, never guessed.</li>
<li><strong>Transcripts:</strong> AI extraction with rules for spoken numbers ("সাড়ে তিন লাখ" → 350000) and spelled-out licence numbers; a regex extractor when no AI is available.</li>
<li><strong>Knowledge base:</strong> split at <code>##</code> headings (up to 900 characters), each passage indexed with a "document › section" context line.</li>
</ul>
<h3>Storage</h3>
<ul>
<li>No database. Records are JSON files: the result, SHA-256 fingerprints of the uploaded files (not the files) and the previous record's hash.</li>
<li>On Render's free plan the disk is reset on every restart (""" + a("render_free", "Render docs") + """), so records there are demo-only.</li>
</ul>
<h3>Privacy</h3>
<ul>
<li><code>ALLOW_REAL_DATA=false</code>: fictional SPECIMEN documents only until legal review and local image masking.</li>
<li>Passport, NID and Bangladeshi phone numbers are masked in text before storage or any AI call.</li>
<li>No accounts, no tracking cookies, no third-party analytics. Usage numbers on this page are counts only.</li>
</ul>"""),
    sec("ai-layer", "tech", "AI layer", live="ai",
        kicker="Three narrow jobs for AI: listen, read, explain. Each one has a fallback and a check.",
        body="""<h3>Models</h3>
<table><thead><tr><th>Job</th><th>Model</th><th>Guard</th></tr></thead><tbody>
<tr><td>Speech to text</td><td>Whisper large-v3 on Groq, Bangla language hint</td><td>Worker corrects the transcript before the check</td></tr>
<tr><td>Read documents</td><td>qwen/qwen3.8-27b, vision + JSON mode (READ_DOCUMENT_V1)</td><td>Text in the image is data, not instructions; never outputs ID numbers; never judges authenticity</td></tr>
<tr><td>Read the promise</td><td>Same model (EXTRACT_PROMISE_V1)</td><td>Evidence quote for every field; offline extractor fallback</td></tr>
<tr><td>Answer rights questions</td><td>Same model (ANSWER_PROMPT_V2)</td><td>Grounding check; falls back to quoting the sources</td></tr>
</tbody></table>
<h3>RAG pipeline</h3>
<ol>
<li>Mask ID numbers; detect the country and any amount paid.</li>
<li>Rewrite the query: Banglish to Bangla, everyday words to legal terms, situations ("বেতন দিচ্ছে না") to the passages that cover them.</li>
<li>Fee questions skip the model: the answer is worked out from the government table.</li>
<li>Hybrid retrieval: weighted BM25 (the user's words count more than added synonyms) + TF-IDF character 3–5-gram vectors, fused with Reciprocal Rank Fusion.</li>
<li>Relevance gate: off-topic questions are refused, not guessed.</li>
<li>The model writes a cited answer from the top 4 passages; the answer is rejected if it cites a passage that does not exist or states a number not in the passages.</li>
</ol>
<p><strong>About the held-out set.</strong> Its 16 questions were written after tuning. On their first run 12 of 16 answers had the key fact (hit@3 was 16/16); the four gaps were then fixed, so the live score below is no longer an unseen test. New held-out questions will be added before the final round.</p>
<p><strong>No GraphRAG.</strong> With 28 passages a graph adds nothing; hybrid retrieval with query rewriting is measured below.</p>
<h3>Personalisation</h3>
<p>None that is stored. Answers adapt to what is in the question (country, amount paid, situation) and nothing is remembered between questions.</p>
<h3>Explainability</h3>
<ul>
<li>Every warning shows the rule ID, what was promised, what was found, the source table or document, the law section and the next step.</li>
<li>Every answer shows its numbered sources, highlighted sentences, a confidence level and how the passages were found.</li>
<li>Every result lists what was <em>not</em> checked, so silence is never read as "safe".</li>
<li>Prompts are versioned in <code>PROMPTS.md</code>.</li>
</ul>"""),
    sec("roadmap", "tech", "Product roadmap",
        kicker="Plans, in the order the risks need them.",
        body="""<h3>Short term · before the final round (December 2026)</h3>
<ul><li>Legal team review of rules, passages and fee figures</li><li>WhatsApp signature check and rate limits</li><li>Dialect voice tests with volunteers</li><li>This live documentation (done)</li></ul>
<h3>Mid term · first half of 2027</h3>
<ul><li>Pilot with one NGO or training centre in a top-sending district</li><li>Local masking of ID numbers on images, then <code>ALLOW_REAL_DATA</code></li><li>Official agency licence data; Postgres for sessions and records</li></ul>
<h3>Long term</h3>
<ul><li>Case files that plug into Probash Bondhu and BMET complaint intake</li><li>More corridors, then other countries that send workers through brokers</li><li>Open rules and knowledge base for public audit</li></ul>"""),
    sec("performance", "tech", "Performance and scalability", live="performance",
        kicker="The limit today is the free AI quota, not the server.",
        body="""<h3>Load expectations</h3>
<ul>
<li>Prototype on Render's free plan: 512 MB RAM, 0.1 CPU, sleeps after 15 idle minutes and takes about a minute to wake (""" + a("render_free", "Render docs") + """).</li>
<li>Groq's free tier allows about 1,000 output tokens per minute for the main model, so a few AI-written answers per minute.</li>
<li>Everything that does not need AI (rules, retrieval, fee answers) runs in milliseconds; see the live numbers below.</li>
</ul>
<h3>Optimisations in place</h3>
<ul>
<li>Phone photos shrunk to 1600 px before sending; short replies (max 800 tokens, reasoning off).</li>
<li>On a rate limit the rights Q&amp;A answers at once from the sources instead of waiting; a 2-minute cooldown after an outage.</li>
<li>Slow steps run in a thread pool; the search index is built once and cached.</li>
<li>One static page, no framework, fonts with <code>display=swap</code>. This page inlines its content and loads diagrams only when they scroll into view.</li>
</ul>
<h3>Scaling path</h3>
<ul><li>Paid AI tier or a self-hosted open model</li><li>A queue for WhatsApp jobs</li><li>Postgres; then several stateless app instances behind the load balancer</li></ul>"""),
    sec("security", "tech", "Security", live="security",
        kicker="What is protected, how, and what is not done yet.",
        body="""<h3>Authentication and roles</h3>
<p>Workers have no accounts. This documentation has two admin roles, each with its own password set on the server (12 characters or more; never in the repository).</p>
<table><thead><tr><th>Action</th><th>Admin</th><th>Super Admin</th></tr></thead><tbody>
<tr><td>Edit sections, save drafts, publish</td><td>Yes</td><td>Yes</td></tr>
<tr><td>Turn /docs on or off, set the publishing window</td><td>Yes</td><td>Yes</td></tr>
<tr><td>Upload team photos</td><td>Yes</td><td>Yes</td></tr>
<tr><td>Restore an old version, reset content or settings</td><td>No</td><td>Yes</td></tr>
<tr><td>Read the audit log</td><td>No</td><td>Yes</td></tr>
</tbody></table>
<p>Sessions are HMAC-signed, HttpOnly, SameSite=Strict cookies that expire after 8 hours. Every change also needs a custom header that a cross-site form cannot send. Sign-in is limited to 5 wrong passwords per address and 40 overall per 15 minutes.</p>
<h3>Data protection</h3>
<ul>
<li>Identity numbers masked in text before storage or AI calls; synthetic data only (<code>ALLOW_REAL_DATA=false</code>).</li>
<li>API keys and passwords only in environment variables; <code>.env</code> is git-ignored.</li>
<li>Prompt-injection defence: text inside a document is treated as data; outputs are forced into a JSON schema.</li>
<li>Editor HTML on this page passes an allowlist cleaner; uploaded photos are re-encoded, which drops EXIF and GPS data.</li>
<li>Records are hash-chained; <code>/health</code> reports whether the chain is intact.</li>
</ul>
<h3>Known gaps</h3>
<ul>
<li>No rate limits on the public endpoints yet.</li>
<li>The WhatsApp webhook does not yet verify Meta's request signature.</li>
<li>Document photos reach the AI provider unmasked, which is why only SPECIMEN documents are allowed.</li>
</ul>"""),
    sec("analytics", "tech", "Analytics", live="analytics",
        kicker="Counts only. No personal data, no cookies, no third-party trackers.",
        body="""<h3>KPIs for the pilot</h3>
<ul>
<li>Checks completed per week, and the share with at least one critical warning</li>
<li>Warnings per rule (which promises break most often, by corridor)</li>
<li>Rights questions answered vs refused (knowledge-base gaps)</li>
<li>AI fallback rate and median time to a result</li>
<li>Actions taken after a warning (with consent): did not pay, asked for a contract, called 16135, filed a complaint</li>
</ul>
<p>Below: what this server has counted since it last started. On the free plan the server restarts when it wakes from sleep, so the counts are small and reset often.</p>"""),
    sec("contributors", "tech", "Team and contributors",
        kicker="Who built it, and whose work it stands on.",
        body="""<ul>
<li><strong>Team Singularity</strong> (see <a href="#team">Team</a>): product, research, legal content, testing and the pitch.</li>
<li>Built with AI coding assistance (Claude). Every change was run, tested and reviewed by the team.</li>
<li>Open models and tools: Whisper large-v3 (OpenAI, served by Groq), Qwen (Alibaba, served by Groq), Bengali.AI regional Whisper (optional local speech model), FastAPI, NumPy, Pillow, Mermaid.</li>
<li>Fonts: Tiro Bangla and Hind Siliguri (SIL Open Font License).</li>
<li>Facts: the newspapers, research groups (RMMRU, OKUP) and government pages linked in the knowledge base.</li>
</ul>"""),
    sec("changelog", "tech", "Changelog", type="changelog",
        kicker="What changed, newest first.",
        body="",
        entries=[
            {"version": "0.2.0", "date": "20 Nov 2026",
             "notes": "<ul><li>Live <code>/docs</code>: pitch deck, technical documentation, live system view (features, endpoints, knowledge base, usage, benchmarks re-run on the server)</li><li>Admin panel: visibility switch, publishing window, editor, drafts, versions, team photos</li><li>Interactive API reference moved from <code>/docs</code> to <code>/api/docs</code></li></ul>"},
            {"version": "0.1.0", "date": "18–20 Nov 2026",
             "notes": "<ul><li>Preliminary submission build: 12 rules with law and next step, voice and document reading on Groq, Promise Records, WhatsApp webhook</li><li>Rights Q&amp;A with hybrid retrieval, fee-table answers and a grounding check; evaluation set</li><li>Passport-themed site, section navigation, logo and icons</li><li>Fix: <code>numpy</code> added to requirements for Render</li></ul>"},
        ]),
]

content = {
    "meta": {
        "title": "Protishruti",
        "tagline": "A voice-first AI that checks a broker's promise against a migrant worker's visa, contract and payslips, before the money is paid.",
        "summary": """<p><strong>For</strong> Bangladeshi migrant workers and their families, about 1.1 million people a year.</p>
<p><strong>Problem:</strong> brokers sell jobs with spoken promises; the papers often say something else, and workers pay far above the government's cost cap.</p>
<p><strong>What it does:</strong> the worker says the promise in Bangla and photographs the papers. Twelve fixed rules compare them and give the law and the next step. AI only listens, reads and explains.</p>
<p><strong>Status:</strong> working prototype on fictional data, live on this server; legal review before real users.</p>""",
        "app_url": "/",
        "repo_url": "https://github.com/rynrafsan/protishruti",
        "version_label": "v0.2 · prototype",
    },
    "sections": sections,
}

if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(ROOT))
    from app.docsite.store import clean_content  # same validation as the admin panel
    clean = clean_content(content)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(clean, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)}: {len(clean['sections'])} sections, {OUT.stat().st_size // 1024} KB")
