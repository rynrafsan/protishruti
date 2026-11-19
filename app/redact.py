"""Mask identity numbers before text is stored or sent to any external API.

Covers text only. Masking numbers on document IMAGES needs a local OCR step
(planned: run a local OCR model, blur detected ID regions before any API call).
"""
import re

BN_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")

PATTERNS = [
    (re.compile(r"\b[A-Z]{1,2}\d{7,8}\b"), "[PASSPORT]"),       # passport-like
    (re.compile(r"\b(?:\d{17}|\d{13}|\d{10})\b"), "[NID]"),       # BD NID: 10/13/17 digits
    (re.compile(r"\b(?:\+?880|0)1[3-9]\d{8}\b"), "[PHONE]"),     # BD mobile numbers
]


def to_ascii_digits(text: str) -> str:
    return text.translate(BN_DIGITS)


def redact(text: str) -> str:
    """Mask ID numbers written in Bangla or English digits; everything else keeps its original script."""
    text = text or ""
    ascii_ = to_ascii_digits(text)  # same length as text, so match positions carry over
    spans = []
    for pat, repl in PATTERNS:
        for m in pat.finditer(ascii_):
            if not any(m.start() < e and s < m.end() for s, e, _ in spans):
                spans.append((m.start(), m.end(), repl))
    out, pos = [], 0
    for s, e, repl in sorted(spans):
        out.append(text[pos:s]); out.append(repl); pos = e
    out.append(text[pos:])
    return "".join(out)
