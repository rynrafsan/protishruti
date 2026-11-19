from datetime import date

from app import rules
from app.extract import heuristic_extract
from app.redact import redact
from app.schema import Fee, Money, Promise


def promise(**kw):
    base = dict(source="voice_note", employer_name="Al Noor Trading", job_title="factory worker",
                country="SA", monthly_salary=Money(amount=35000, currency="BDT"),
                fees_paid=[Fee(amount_bdt=150000)], agency_license_no="RL-9001",
                has_written_contract=True)
    base.update(kw)
    return Promise(**base)


def contract(**kw):
    base = dict(source="contract", employer_name="Al Noor Trading", job_title="factory worker",
                country="SA", monthly_salary=Money(amount=1100, currency="SAR"))
    base.update(kw)
    return Promise(**base)


def ids(flags):
    return {f.rule_id for f in flags}


def test_clean_case_has_no_critical_flags():
    flags = rules.run_rules(promise(), [contract()])
    assert not [f for f in flags if f.severity == "critical"]


def test_job_mismatch():
    assert "R01" in ids(rules.run_rules(promise(), [contract(job_title="cleaner")]))


def test_domestic_visa():
    visa = Promise(source="visa", visa_category="domestic worker")
    assert "R02" in ids(rules.run_rules(promise(), [visa, contract()]))


def test_salary_below_promise():
    assert "R04" in ids(rules.run_rules(promise(), [contract(monthly_salary=Money(amount=600, currency="SAR"))]))


def test_fee_above_cap():
    assert "R05" in ids(rules.run_rules(promise(fees_paid=[Fee(amount_bdt=400000)]), [contract()]))


def test_unknown_and_suspended_agency():
    assert "R06" in ids(rules.r06_agency(promise(agency_license_no="RL-0000"), []))
    assert "R06" in ids(rules.r06_agency(promise(agency_license_no="RL-9002"), []))


def test_expired_agency_licence():
    flags = rules.r06_agency(promise(agency_license_no="RL-9003"), [], today=date(2026, 11, 18))
    assert flags and flags[0].severity == "critical"


def test_no_contract():
    assert "R07" in ids(rules.run_rules(promise(has_written_contract=False), []))


def test_payslip_underpaid_and_late():
    slip = Promise(source="payslip", monthly_salary=Money(amount=700, currency="SAR"),
                   salary_delay_days=45, pay_period="2027-03")
    got = ids(rules.run_rules(promise(), [contract()], [slip]))
    assert {"R10", "R12"} <= got


def test_not_checked_always_lists_authenticity():
    assert any("genuine" in x for x in rules.not_checked(promise(), [contract()]))


def test_redaction():
    out = redact("পাসপোর্ট A01234567, NID 1234567890123, ফোন 01712345678")
    assert "[PASSPORT]" in out and "[NID]" in out and "[PHONE]" in out


def test_heuristic_extract_bangla():
    t = "সৌদিতে ফ্যাক্টরির কাজ। বেতন ৩৫ হাজার টাকা। আমি মোট ৪ লাখ টাকা দিয়েছি। লাইসেন্স RL-9001"
    p = heuristic_extract(t)
    assert p.country == "SA" and p.job_title == "factory worker"
    assert p.monthly_salary.amount == 35000
    assert p.total_fees_bdt() == 400000
    assert p.agency_license_no == "RL-9001"
