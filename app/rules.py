"""Rules engine: the ONLY component that raises flags. Pure Python, no AI, fully testable.

Each rule compares the worker's promise (from voice notes) with what the documents
and payslips say, or with official reference data (cost caps, agency registry).
"""
from __future__ import annotations

import csv
import re
import json
from datetime import date, datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional

from .schema import Flag, Promise

DATA = Path(__file__).resolve().parent.parent / "data"

# ---------- reference data ----------

def _load_json(name: str) -> dict:
    return json.loads((DATA / name).read_text(encoding="utf-8"))


COST_CAPS = _load_json("cost_caps.json")["caps_bdt"]
FX = _load_json("fx_rates.json")["bdt_per_unit"]
WATCHLIST = _load_json("watchlist.json")["countries"]


def load_agencies(path: Path | None = None) -> dict[str, dict]:
    path = path or DATA / "agencies_sample.csv"
    with open(path, newline="", encoding="utf-8") as f:
        return {row["license_no"].strip().upper(): row for row in csv.DictReader(f)}


AGENCIES = load_agencies()

# ---------- helpers ----------

JOB_CATEGORIES = {
    "domestic": ["domestic", "housemaid", "house maid", "driver (house)", "খাদেম", "গৃহকর্মী", "عاملة منزلية", "منزلي"],
    "cleaning": ["cleaner", "cleaning", "ক্লিনার", "পরিচ্ছন্ন", "عامل نظافة", "نظافة"],
    "factory": ["factory", "production", "operator", "ফ্যাক্টরি", "কারখানা", "مصنع", "عامل إنتاج"],
    "construction": ["construction", "mason", "labour", "laborer", "নির্মাণ", "রাজমিস্ত্রি", "بناء", "عامل"],
    "driver": ["driver", "ড্রাইভার", "سائق"],
    "agriculture": ["farm", "agricultur", "plantation", "কৃষি", "زراعة"],
    "hospitality": ["hotel", "restaurant", "waiter", "cook", "হোটেল", "مطعم", "طباخ"],
}


def job_category(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    t = text.lower()
    for cat, words in JOB_CATEGORIES.items():
        if any(w in t for w in words):
            return cat
    return None


def to_bdt(amount: Optional[float], currency: Optional[str]) -> Optional[float]:
    if amount is None or not currency:
        return None
    rate = FX.get(currency.upper())
    return amount * rate if rate else None


def _norm_name(s: str) -> str:
    s = re.sub(r"\(.*?\)", " ", s.lower())
    s = re.sub(r"\b(co|company|ltd|llc|est|establishment|trading|the)\b\.?", " ", s)
    return " ".join(re.sub(r"[^\w\s]", " ", s).split())


def similar(a: str, b: str) -> float:
    """Name similarity in [0, 1]. Containment (e.g. 'Al Noor' in 'Al Noor Trading') counts as a match."""
    x, y = _norm_name(a), _norm_name(b)
    if not x or not y:
        return 0.0
    if x in y or y in x:
        return 1.0
    return SequenceMatcher(None, x, y).ratio()


def _first(docs: list[Promise], attr: str):
    for d in docs:
        v = getattr(d, attr)
        if hasattr(v, "amount") and v.amount is None:  # empty Money
            continue
        if v not in (None, "", []):
            return v, d
    return None, None

# ---------- rules ----------

def r01_job_mismatch(p: Promise, docs: list[Promise]) -> list[Flag]:
    doc_job, d = _first(docs, "job_title")
    pc, dc = job_category(p.job_title), job_category(doc_job)
    if pc and dc and pc != dc:
        return [Flag(rule_id="R01", severity="critical",
                     title_en="Job on the documents differs from the promised job",
                     title_bn="কাগজে লেখা কাজ আর প্রতিশ্রুত কাজ আলাদা",
                     promised=p.job_title, found=doc_job, source=f"{d.source} document")]
    return []


def r02_visa_type(p: Promise, docs: list[Promise]) -> list[Flag]:
    visa, d = _first(docs, "visa_category")
    if visa and job_category(visa) == "domestic" and job_category(p.job_title) not in (None, "domestic"):
        return [Flag(rule_id="R02", severity="critical",
                     title_en="Domestic-worker visa, but a company job was promised",
                     title_bn="গৃহকর্মীর ভিসা, অথচ কোম্পানির চাকরির প্রতিশ্রুতি দেওয়া হয়েছে",
                     promised=p.job_title, found=visa, source=f"{d.source} document")]
    return []


def r03_employer(p: Promise, docs: list[Promise]) -> list[Flag]:
    names = [(d.employer_name, d) for d in docs if d.employer_name]
    flags: list[Flag] = []
    if p.employer_name:
        for name, d in names:
            if similar(p.employer_name, name) < 0.6:
                flags.append(Flag(rule_id="R03", severity="warning",
                                  title_en="Employer name differs from what was promised",
                                  title_bn="নিয়োগকর্তার নাম প্রতিশ্রুতির সাথে মেলে না",
                                  promised=p.employer_name, found=name, source=f"{d.source} document"))
                break
    # documents disagreeing with each other
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            if similar(names[i][0], names[j][0]) < 0.6:
                flags.append(Flag(rule_id="R03", severity="critical",
                                  title_en="Documents name different employers",
                                  title_bn="বিভিন্ন কাগজে বিভিন্ন নিয়োগকর্তার নাম",
                                  promised=names[i][0], found=names[j][0],
                                  source=f"{names[i][1].source} vs {names[j][1].source}"))
                return flags
    return flags


def r04_salary(p: Promise, docs: list[Promise]) -> list[Flag]:
    sal, d = _first(docs, "monthly_salary")
    if not sal or sal.amount is None:
        return []
    promised = to_bdt(p.monthly_salary.amount, p.monthly_salary.currency)
    found = to_bdt(sal.amount, sal.currency)
    if promised and found and found < promised * 0.95:
        return [Flag(rule_id="R04", severity="critical",
                     title_en="Salary on the documents is lower than promised",
                     title_bn="কাগজে বেতন প্রতিশ্রুতির চেয়ে কম",
                     promised=f"{p.monthly_salary.amount:g} {p.monthly_salary.currency}",
                     found=f"{sal.amount:g} {sal.currency} (about {found:,.0f} BDT vs {promised:,.0f} BDT)",
                     source=f"{d.source} document; approximate exchange rates in data/fx_rates.json")]
    return []


def r05_fee_cap(p: Promise, docs: list[Promise]) -> list[Flag]:
    country = p.country or _first(docs, "country")[0]
    paid = p.total_fees_bdt()
    cap = COST_CAPS.get((country or "").upper())
    if cap and paid > cap:
        return [Flag(rule_id="R05", severity="critical",
                     title_en="Fees paid are above the government cap",
                     title_bn="সরকার-নির্ধারিত খরচের চেয়ে বেশি টাকা নেওয়া হয়েছে",
                     promised=f"Cap for {country}: {cap:,.0f} BDT", found=f"Paid: {paid:,.0f} BDT",
                     source="Government migration cost table (data/cost_caps.json)")]
    return []


def r06_agency(p: Promise, docs: list[Promise], agencies: dict | None = None,
               today: date | None = None) -> list[Flag]:
    agencies = agencies if agencies is not None else AGENCIES
    today = today or date.today()
    lic = p.agency_license_no or _first(docs, "agency_license_no")[0]
    if not lic:
        return [Flag(rule_id="R06", severity="warning",
                     title_en="No recruiting agency licence number given",
                     title_bn="রিক্রুটিং এজেন্সির লাইসেন্স নম্বর দেওয়া হয়নি",
                     source="Ask the broker for the RL number and check it on the official agency list")]
    row = agencies.get(lic.strip().upper())
    if not row:
        return [Flag(rule_id="R06", severity="critical",
                     title_en="Agency licence not found in the agency list",
                     title_bn="এজেন্সির লাইসেন্স তালিকায় পাওয়া যায়নি",
                     found=lic, source="Agency registry snapshot (data/agencies_*.csv)")]
    expired = row.get("valid_until") and datetime.strptime(row["valid_until"], "%Y-%m-%d").date() < today
    if row["status"].lower() != "active" or expired:
        return [Flag(rule_id="R06", severity="critical",
                     title_en="Agency licence is not active",
                     title_bn="এজেন্সির লাইসেন্স সক্রিয় নয়",
                     found=f"{lic}: {row['status']}, valid until {row.get('valid_until')}",
                     source="Agency registry snapshot (data/agencies_*.csv)")]
    return []


def r07_no_contract(p: Promise, docs: list[Promise]) -> list[Flag]:
    has_contract = any(d.source == "contract" for d in docs) or p.has_written_contract
    if not has_contract:
        return [Flag(rule_id="R07", severity="warning",
                     title_en="No written employment contract provided",
                     title_bn="লিখিত চাকরির চুক্তিপত্র নেই",
                     source="Ask for a signed contract before paying or flying")]
    return []


def r08_watchlist(p: Promise, docs: list[Promise]) -> list[Flag]:
    country = (p.country or _first(docs, "country")[0] or "").upper()
    if country in WATCHLIST:
        return [Flag(rule_id="R08", severity="info",
                     title_en="Destination has widely reported recruitment fraud",
                     title_bn="এই দেশে নিয়োগ প্রতারণার অনেক খবর রয়েছে",
                     found=country, source=WATCHLIST[country])]
    return []


def r09_visa_expiry(p: Promise, docs: list[Promise], today: date | None = None) -> list[Flag]:
    today = today or date.today()
    exp, d = _first(docs, "visa_expiry")
    if not exp:
        return []
    try:
        exp_d = datetime.strptime(exp, "%Y-%m-%d").date()
    except ValueError:
        return []
    days = (exp_d - today).days
    if days < 30:
        return [Flag(rule_id="R09", severity="critical" if days < 0 else "warning",
                     title_en="Visa has expired or expires within 30 days",
                     title_bn="ভিসার মেয়াদ শেষ বা ৩০ দিনের মধ্যে শেষ হবে",
                     found=exp, source=f"{d.source} document")]
    return []


def r10_payslip_salary(p: Promise, docs: list[Promise], slips: list[Promise]) -> list[Flag]:
    contract_sal, _ = _first(docs, "monthly_salary")
    base = contract_sal if contract_sal and contract_sal.amount else p.monthly_salary
    expected = to_bdt(base.amount, base.currency)
    flags = []
    for s in slips:
        got = to_bdt(s.monthly_salary.amount, s.monthly_salary.currency)
        if expected and got and got < expected * 0.95:
            flags.append(Flag(rule_id="R10", severity="critical",
                              title_en="Paid less than the contract salary",
                              title_bn="চুক্তির চেয়ে কম বেতন দেওয়া হয়েছে",
                              promised=f"{base.amount:g} {base.currency}",
                              found=f"{s.monthly_salary.amount:g} {s.monthly_salary.currency} ({s.pay_period or 'unknown month'})",
                              source="Payslip vs contract"))
    return flags


def r11_deductions(p: Promise, docs: list[Promise], slips: list[Promise]) -> list[Flag]:
    flags = []
    for s in slips:
        if s.deductions_amount and s.monthly_salary.amount and s.deductions_amount > 0.1 * s.monthly_salary.amount:
            flags.append(Flag(rule_id="R11", severity="warning",
                              title_en="Large deduction from salary; check if it is lawful",
                              title_bn="বেতন থেকে বড় অঙ্কের টাকা কাটা হয়েছে; বৈধ কি না যাচাই করুন",
                              found=f"{s.deductions_amount:g} {s.monthly_salary.currency} ({s.deductions_reason or 'no reason given'})",
                              source="Payslip; lawful deductions depend on destination labour law"))
    return flags


def r12_late_salary(p: Promise, docs: list[Promise], slips: list[Promise]) -> list[Flag]:
    return [Flag(rule_id="R12", severity="critical",
                 title_en="Salary paid more than 30 days late",
                 title_bn="বেতন ৩০ দিনের বেশি দেরিতে দেওয়া হয়েছে",
                 found=f"{s.salary_delay_days} days ({s.pay_period or 'unknown month'})",
                 source="Payslip / salary SMS dates")
            for s in slips if s.salary_delay_days and s.salary_delay_days > 30]


PRE_DEPARTURE_RULES = [r01_job_mismatch, r02_visa_type, r03_employer, r04_salary, r05_fee_cap,
                       r06_agency, r07_no_contract, r08_watchlist, r09_visa_expiry]
POST_ARRIVAL_RULES = [r10_payslip_salary, r11_deductions, r12_late_salary]


def run_rules(promise: Promise, docs: list[Promise], slips: list[Promise] | None = None) -> list[Flag]:
    slips = slips or []
    flags: list[Flag] = []
    for rule in PRE_DEPARTURE_RULES:
        flags += rule(promise, docs)
    for rule in POST_ARRIVAL_RULES:
        flags += rule(promise, docs, slips)
    order = {"critical": 0, "warning": 1, "info": 2}
    return sorted(flags, key=lambda f: order[f.severity])


def not_checked(promise: Promise, docs: list[Promise]) -> list[str]:
    """What the system could NOT verify. Always shown to the user (no false reassurance)."""
    items = ["Whether the documents are genuine (use the official visa check and the agency registry)",
             "Real working and living conditions at the employer"]
    if not docs:
        items.insert(0, "No documents were provided, so nothing could be compared")
    for d in docs:
        items += [f"Unreadable on {d.source}: {f}" for f in d.unreadable_fields]
    return items
