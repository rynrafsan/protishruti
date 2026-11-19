"""Promise schema: every input (voice note, document, payslip) is converted into this shape."""
from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, Field

SourceType = Literal["voice_note", "visa", "contract", "demand_letter", "payslip", "manual"]


class Money(BaseModel):
    amount: Optional[float] = None
    currency: Optional[str] = None  # ISO code: SAR, MYR, QAR, BDT ...


class Fee(BaseModel):
    amount_bdt: Optional[float] = None
    paid_to: Optional[str] = None  # broker | agency | other
    date: Optional[str] = None


class Evidence(BaseModel):
    field: str
    span: Optional[str] = None          # exact words / text that support the field
    bbox: Optional[list[float]] = None  # [x0, y0, x1, y1] on the document image
    confidence: float = 0.0


class Promise(BaseModel):
    source: SourceType = "manual"
    employer_name: Optional[str] = None
    job_title: Optional[str] = None
    visa_category: Optional[str] = None   # e.g. "company worker", "domestic worker"
    country: Optional[str] = None          # ISO-2: SA, MY, QA ...
    monthly_salary: Money = Field(default_factory=Money)
    hours_per_day: Optional[float] = None
    contract_months: Optional[int] = None
    fees_paid: list[Fee] = Field(default_factory=list)
    agency_license_no: Optional[str] = None
    visa_expiry: Optional[str] = None      # YYYY-MM-DD
    has_written_contract: Optional[bool] = None
    # payslip-only fields
    pay_period: Optional[str] = None           # YYYY-MM
    deductions_amount: Optional[float] = None   # in the salary currency
    deductions_reason: Optional[str] = None
    salary_delay_days: Optional[int] = None
    evidence: list[Evidence] = Field(default_factory=list)
    unreadable_fields: list[str] = Field(default_factory=list)

    def total_fees_bdt(self) -> float:
        return float(sum(f.amount_bdt or 0 for f in self.fees_paid))


class Flag(BaseModel):
    rule_id: str
    severity: Literal["critical", "warning", "info"]
    title_en: str
    title_bn: str
    promised: Optional[str] = None
    found: Optional[str] = None
    source: str  # the law / table / document the flag rests on
    law_bn: Optional[str] = None     # what the law says (plain Bangla), from app/legal.py
    action_bn: Optional[str] = None  # where to go next


class CheckResult(BaseModel):
    transcript: Optional[str] = None  # what was heard or typed (ID numbers masked)
    promise: Promise
    documents: list[Promise]
    payslips: list[Promise] = Field(default_factory=list)
    flags: list[Flag]
    not_checked: list[str]
    explanation_bn: str
    record_id: Optional[str] = None
    record_hash: Optional[str] = None


# ---------------------------------------------------------------------------
# Turning model output into a Promise without crashing
# ---------------------------------------------------------------------------
_COUNTRY_NAMES = {
    "saudi arabia": "SA", "ksa": "SA", "saudi": "SA", "malaysia": "MY", "qatar": "QA", "oman": "OM",
    "united arab emirates": "AE", "uae": "AE", "kuwait": "KW", "bahrain": "BH", "singapore": "SG",
    "jordan": "JO", "lebanon": "LB", "russia": "RU", "cambodia": "KH", "bangladesh": "BD",
}


def _num(v):
    """'35,000 SAR' -> 35000.0; numbers pass through; anything else -> None."""
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        import re
        m = re.search(r"-?\d[\d,]*(?:\.\d+)?", v.replace(" ", " "))
        return float(m.group(0).replace(",", "")) if m else None
    return None


def _bool(v):
    if isinstance(v, bool) or v is None:
        return v
    if isinstance(v, str):
        s = v.strip().lower()
        if s in {"true", "yes", "y", "1"}:
            return True
        if s in {"false", "no", "n", "0"}:
            return False
    return None


def _clean(data: dict) -> dict:
    """Coerce common model slips (number instead of object, names instead of ISO codes...)."""
    out = {k: v for k, v in data.items() if k in Promise.model_fields}

    sal = out.get("monthly_salary")
    if sal is not None and not isinstance(sal, dict):
        import re
        cur = re.search(r"\b([A-Z]{3})\b", sal) if isinstance(sal, str) else None
        out["monthly_salary"] = {"amount": _num(sal), "currency": cur.group(1) if cur else None}
    elif isinstance(sal, dict):
        out["monthly_salary"] = {"amount": _num(sal.get("amount")), "currency": sal.get("currency")}

    fees = out.get("fees_paid")
    if fees is not None:
        if not isinstance(fees, list):
            fees = [fees]
        clean_fees = []
        for f in fees:
            if isinstance(f, dict):
                clean_fees.append({"amount_bdt": _num(f.get("amount_bdt", f.get("amount"))),
                                   "paid_to": f.get("paid_to"), "date": f.get("date")})
            elif _num(f) is not None:
                clean_fees.append({"amount_bdt": _num(f)})
        out["fees_paid"] = clean_fees

    c = out.get("country")
    if isinstance(c, str):
        c = c.strip()
        out["country"] = c.upper() if len(c) == 2 else _COUNTRY_NAMES.get(c.lower(), None)

    for k in ("hours_per_day", "deductions_amount"):
        if k in out:
            out[k] = _num(out[k])
    for k in ("contract_months", "salary_delay_days"):
        if k in out:
            n = _num(out[k])
            out[k] = int(round(n)) if n is not None else None
    if "has_written_contract" in out:
        out["has_written_contract"] = _bool(out["has_written_contract"])

    ev = out.get("evidence")
    if ev is not None:
        items = []
        for e in ev if isinstance(ev, list) else []:
            if isinstance(e, dict) and e.get("field"):
                items.append({"field": str(e["field"]), "span": None if e.get("span") is None else str(e["span"]),
                              "confidence": _num(e.get("confidence")) or 0.0})
        out["evidence"] = items

    uf = out.get("unreadable_fields")
    if uf is not None:
        out["unreadable_fields"] = [str(x) for x in uf] if isinstance(uf, list) else [str(uf)]
    return out


def promise_from_model_output(data: dict, source: str) -> Promise:
    """Validate model JSON into a Promise. Fields that still fail are moved to unreadable_fields."""
    from pydantic import ValidationError

    if not isinstance(data, dict):
        return Promise(source=source, unreadable_fields=["all fields (model returned no object)"])
    out = _clean(data)
    out["source"] = source
    for _ in range(len(Promise.model_fields)):
        try:
            return Promise.model_validate(out)
        except ValidationError as e:
            bad = {str(err["loc"][0]) for err in e.errors() if err.get("loc")}
            if not bad or "source" in bad:
                raise
            for k in bad:
                out.pop(k, None)
            out["unreadable_fields"] = list(out.get("unreadable_fields", [])) + sorted(bad)
    return Promise(source=source, unreadable_fields=["all fields (could not validate model output)"])
