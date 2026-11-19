"""Turn a voice-note transcript into a Promise (LLM, with an offline fallback)."""
from __future__ import annotations

import logging
import re
import unicodedata

from . import config, llm, prompts
from .redact import redact, to_ascii_digits
from .schema import Evidence, Fee, Money, Promise, promise_from_model_output

log = logging.getLogger("protishruti")

COUNTRY_WORDS = {
    "SA": ["সৌদি", "saudi", "রিয়াদ", "riyadh", "জেদ্দা", "jeddah"],
    "MY": ["মালয়েশিয়া", "মালয়েশিয়া", "malaysia"],
    "QA": ["কাতার", "qatar", "দোহা"],
    "AE": ["দুবাই", "dubai", "আমিরাত", "uae"],
    "OM": ["ওমান", "oman"],
    "KW": ["কুয়েত", "কুয়েত", "kuwait"],
    "RU": ["রাশিয়া", "রাশিয়া", "russia"],
    "BH": ["বাহরাইন", "bahrain"],
    "JO": ["জর্ডান", "jordan"],
    "LB": ["লেবানন", "lebanon"],
    "IQ": ["ইরাক", "iraq"],
    "LY": ["লিবিয়া", "লিবিয়া", "libya"],
    "EG": ["মিসর", "মিশর", "egypt"],
    "MV": ["মালদ্বীপ", "maldives"],
    "BN": ["ব্রুনাই", "brunei"],
}
JOB_WORDS = {
    "factory worker": ["ফ্যাক্টরি", "কারখানা", "factory"],
    "cleaner": ["ক্লিনার", "পরিচ্ছন্ন", "cleaner"],
    "driver": ["ড্রাইভার", "driver"],
    "construction worker": ["নির্মাণ", "construction"],
    "domestic worker": ["বাসাবাড়ি", "গৃহকর্মী", "housemaid"],
    "hotel worker": ["হোটেল", "রেস্টুরেন্ট", "hotel"],
}


def _amount(num: str, unit: str | None) -> float:
    n = float(num.replace(",", ""))
    if unit and unit in ("লাখ", "lakh", "lac"):
        n *= 100_000
    elif unit and unit in ("হাজার", "thousand", "k"):
        n *= 1_000
    return n


AMOUNT = r"(\d[\d,]*(?:\.\d+)?)\s*(লাখ|lakh|lac|হাজার|thousand|k)?"


def heuristic_extract(transcript: str) -> Promise:
    """Offline fallback: keyword and number patterns. Good enough for demos and tests only."""
    t = unicodedata.normalize("NFC", to_ascii_digits(transcript)).lower()
    p = Promise(source="voice_note")
    for code, words in COUNTRY_WORDS.items():
        if any(unicodedata.normalize("NFC", w).lower() in t for w in words):
            p.country = code
            break
    for job, words in JOB_WORDS.items():
        words = [unicodedata.normalize("NFC", w) for w in words]
        if any(w.lower() in t for w in words):
            p.job_title = job
            p.evidence.append(Evidence(field="job_title", span=next(w for w in words if w.lower() in t), confidence=0.5))
            break
    m = re.search(r"(?:বেতন|salary)\D{0,15}" + AMOUNT, t)
    if m:
        p.monthly_salary = Money(amount=_amount(m.group(1), m.group(2)), currency="BDT")
        p.evidence.append(Evidence(field="monthly_salary", span=m.group(0), confidence=0.5))
    paid_words = unicodedata.normalize("NFC", "খরচ|দিয়েছি|দিলাম|নিয়েছে|নিছে|fee|paid|cost")
    fee_patterns = [rf"(?:{paid_words})\D{{0,15}}" + AMOUNT,                    # "paid 4 lakh"
                    AMOUNT + rf"\s*(?:টাকা|taka|tk)?\s*(?:{paid_words})"]      # "৪ লাখ টাকা দিয়েছি"
    seen = set()
    for pat in fee_patterns:
        for m in re.finditer(pat, t):
            if m.start(1) in seen:
                continue
            amt = _amount(m.group(1), m.group(2))
            if amt >= 10_000:
                seen.add(m.start(1))
                p.fees_paid.append(Fee(amount_bdt=amt, paid_to="broker"))
                p.evidence.append(Evidence(field="fees_paid", span=m.group(0), confidence=0.5))
    m = re.search(r"\brl[-\s]?(\d{3,4})\b", t)
    if m:
        p.agency_license_no = f"RL-{m.group(1)}"
    m = re.search(r"(?:কোম্পানি|company)\s+([^\s,।]+(?:\s+[^\s,।]+)?)", transcript, re.I)
    if m:
        p.employer_name = m.group(1)
    if any(w in t for w in ["চুক্তি নাই", "চুক্তিপত্র নাই", "কোনো কাগজ দেয় নাই", "no contract"]):
        p.has_written_contract = False
    return p


def extract_promise(transcript: str, from_voice: bool = False) -> Promise:
    """Typed text: offline extractor unless LLM_EXTRACT. Speech-to-text output (numbers spoken as
    words, "আর এল নাইন..." for RL-9001) goes to the AI by default, with the offline one as fallback."""
    clean = redact(transcript)
    use_ai = config.LLM_EXTRACT or (from_voice and config.LLM_EXTRACT_VOICE)
    if config.LLM_PROVIDER == "mock" or not use_ai:
        return heuristic_extract(clean)
    try:
        data = llm.call(prompts.EXTRACT_PROMISE_V1, f"Transcript:\n{clean}")
        return promise_from_model_output(data, "voice_note")
    except Exception:  # API down, quota, bad JSON: fall back to the offline extractor
        log.exception("LLM extraction failed; using heuristic extractor")
        return heuristic_extract(clean)
