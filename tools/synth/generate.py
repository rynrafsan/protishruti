"""Generate synthetic Protishruti test cases with ONE planted mismatch each.

Usage:
    python tools/synth/generate.py --n 200 --out data/synthetic --seed 7

Each case folder contains:
    transcript_bn.txt   broker promise as the worker would say it (standard Bangla;
                        record dialect versions with real volunteers using this script)
    promise.json        ground-truth promise fields
    visa.json, contract.json   ground-truth document fields (also usable as uploads in mock mode)
    visa.html           SPECIMEN-watermarked rendering (fictional; render to PNG with render.py)
    label.json          the planted rule and expected flags
All names and companies are fictional. Never copy real seals, logos or ID formats.
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

COUNTRIES = {"SA": ("সৌদি আরব", "SAR", 1000, 1500), "MY": ("মালয়েশিয়া", "MYR", 1500, 1800),
             "QA": ("কাতার", "QAR", 1000, 1400), "AE": ("দুবাই", "AED", 1000, 1500)}
JOBS = {"factory worker": ("ফ্যাক্টরির কাজ", "عامل إنتاج"), "cleaner": ("ক্লিনারের কাজ", "عامل نظافة"),
        "driver": ("ড্রাইভারের কাজ", "سائق"), "construction worker": ("নির্মাণের কাজ", "عامل بناء")}
FAKE_COMPANIES = ["Al Noor Trading (FICTIONAL)", "Green Palm Industries (FICTIONAL)",
                  "Desert Star Contracting (FICTIONAL)", "Blue Gulf Services (FICTIONAL)"]
CAPS = {"SA": 165000, "MY": 78990, "QA": 100780, "AE": 107780}
RULES = ["R01", "R02", "R03", "R04", "R05", "R06", "R07", "NONE"]
BN = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")


def bn(n) -> str:
    return str(n).translate(BN)


def make_case(i: int, rng: random.Random) -> dict:
    cc = rng.choice(list(COUNTRIES))
    cname_bn, cur, lo, hi = COUNTRIES[cc]
    job = rng.choice(list(JOBS))
    company = rng.choice(FAKE_COMPANIES)
    salary_local = rng.randrange(lo, hi, 50)
    fx = {"SAR": 32, "MYR": 27, "QAR": 33, "AED": 33}[cur]
    salary_bdt = round(salary_local * fx, -3)
    fee = rng.randrange(CAPS[cc] - 40000, CAPS[cc], 5000)
    planted = RULES[i % len(RULES)]

    promise = {"source": "voice_note", "employer_name": company, "job_title": job, "country": cc,
               "monthly_salary": {"amount": salary_bdt, "currency": "BDT"},
               "fees_paid": [{"amount_bdt": fee, "paid_to": "broker"}], "agency_license_no": "RL-9001",
               "has_written_contract": True}
    visa = {"source": "visa", "employer_name": company, "job_title": job, "visa_category": "company worker",
            "country": cc, "visa_expiry": "2027-12-31"}
    contract = {"source": "contract", "employer_name": company, "job_title": job, "country": cc,
                "monthly_salary": {"amount": salary_local, "currency": cur}, "contract_months": 24,
                "agency_license_no": "RL-9001"}

    if planted == "R01":
        other = rng.choice([j for j in JOBS if j != job])
        visa["job_title"] = contract["job_title"] = other
    elif planted == "R02":
        visa["visa_category"] = "domestic worker"
    elif planted == "R03":
        visa["employer_name"] = contract["employer_name"] = rng.choice([c for c in FAKE_COMPANIES if c != company])
    elif planted == "R04":
        contract["monthly_salary"]["amount"] = int(salary_local * 0.6)
    elif planted == "R05":
        promise["fees_paid"][0]["amount_bdt"] = CAPS[cc] * rng.choice([2, 3, 4])
    elif planted == "R06":
        promise["agency_license_no"] = contract["agency_license_no"] = "RL-9002"  # suspended in sample CSV
    elif planted == "R07":
        promise["has_written_contract"] = False
        contract = None

    total_fee = promise["fees_paid"][0]["amount_bdt"]
    transcript = (f"দালাল ভাই বলছে {cname_bn}তে {JOBS[job][0]}, কোম্পানি {company.split(' (')[0]}। "
                  f"বেতন {bn(int(salary_bdt))} টাকা মাসে। আমি মোট {bn(int(total_fee))} টাকা দিয়েছি। "
                  f"এজেন্সির লাইসেন্স {promise['agency_license_no']}।"
                  + (" কোনো চুক্তিপত্র দেয় নাই।" if planted == "R07" else ""))
    return {"id": f"case_{i:04d}", "planted": planted, "promise": promise, "visa": visa,
            "contract": contract, "transcript": transcript, "arabic_job": JOBS[visa["job_title"]][1]}


def visa_html(case: dict) -> str:
    v = case["visa"]
    return f"""<!doctype html><html><meta charset="utf-8"><style>
body{{font-family:'Noto Naskh Arabic','Noto Sans',sans-serif;width:800px;height:500px;position:relative;border:2px solid #333;padding:24px}}
.wm{{position:absolute;top:180px;left:80px;font-size:96px;color:rgba(200,0,0,.25);transform:rotate(-20deg)}}
td{{padding:6px 12px}}</style>
<div class="wm">SPECIMEN</div>
<h2>Work Visa / تأشيرة عمل — TEST DOCUMENT</h2>
<table>
<tr><td>Employer / صاحب العمل</td><td>{v['employer_name']}</td></tr>
<tr><td>Profession / المهنة</td><td>{case['arabic_job']} ({v['job_title']})</td></tr>
<tr><td>Visa type / نوع التأشيرة</td><td>{v['visa_category']}</td></tr>
<tr><td>Country</td><td>{v['country']}</td></tr>
<tr><td>Valid until / صالحة حتى</td><td>{v['visa_expiry']}</td></tr>
</table><p>Fictional document generated for testing Protishruti. Not valid for travel.</p></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--out", default="data/synthetic")
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    rng = random.Random(a.seed)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    index = []
    for i in range(a.n):
        c = make_case(i, rng)
        d = out / c["id"]
        d.mkdir(exist_ok=True)
        (d / "transcript_bn.txt").write_text(c["transcript"], encoding="utf-8")
        (d / "promise.json").write_text(json.dumps(c["promise"], ensure_ascii=False, indent=2), encoding="utf-8")
        (d / "visa.json").write_text(json.dumps(c["visa"], ensure_ascii=False, indent=2), encoding="utf-8")
        if c["contract"]:
            (d / "contract.json").write_text(json.dumps(c["contract"], ensure_ascii=False, indent=2), encoding="utf-8")
        (d / "visa.html").write_text(visa_html(c), encoding="utf-8")
        (d / "label.json").write_text(json.dumps({"planted_rule": c["planted"]}), encoding="utf-8")
        index.append({"id": c["id"], "planted_rule": c["planted"]})
    (out / "index.json").write_text(json.dumps(index, indent=2))
    print(f"Wrote {a.n} cases to {out}")


if __name__ == "__main__":
    main()
