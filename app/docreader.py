"""Read documents (visa, contract, demand letter, payslip) into a Promise.

- Images/PDF pages -> vision LLM (Gemini or Claude; or swap in Qwen3-VL served locally).
- .json uploads    -> treated as already-extracted fields (used for synthetic test cases
                      and for the offline mock mode).
"""
from __future__ import annotations

import json

from . import config, llm, prompts
from .schema import Promise, promise_from_model_output

DOC_TYPES = {"visa", "contract", "demand_letter", "payslip"}
MAX_SIDE = 1600        # px; enough to read a form, small enough for free-tier upload limits
MAX_BYTES = 3_000_000  # Groq rejects base64 images above ~4 MB


def shrink_image(data: bytes, mime: str | None) -> tuple[bytes, str]:
    """Resize/re-encode large photos to JPEG. Returns the input unchanged if Pillow is missing."""
    try:
        from io import BytesIO
        from PIL import Image, ImageOps
    except ImportError:
        return data, mime or "image/jpeg"
    try:
        img = Image.open(BytesIO(data))
    except Exception:
        raise ValueError("not an image the reader can open (send a JPG or PNG photo)")
    if max(img.size) <= MAX_SIDE and len(data) <= MAX_BYTES and (mime or "") in ("image/jpeg", "image/png"):
        return data, mime
    img = ImageOps.exif_transpose(img).convert("RGB")
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    out = BytesIO()
    img.save(out, format="JPEG", quality=85)
    return out.getvalue(), "image/jpeg"


def read_document(data: bytes, filename: str, mime: str | None, hint: str | None = None) -> Promise:
    name = (filename or "").lower()
    if name.endswith(".json"):
        fields = json.loads(data.decode("utf-8"))
        fields.setdefault("source", hint or fields.pop("doc_type", "contract"))
        fields.pop("doc_type", None)
        return Promise.model_validate(fields)

    if config.LLM_PROVIDER == "mock":
        return Promise(source=hint if hint in DOC_TYPES else "contract",
                       unreadable_fields=["all fields (mock mode cannot read images; set LLM_PROVIDER)"])

    # Data safety rule: until ALLOW_REAL_DATA=true (after legal review + local masking),
    # only synthetic SPECIMEN documents may be sent to external APIs. The UI says so.
    data, mime = shrink_image(data, mime)
    out = llm.call(prompts.READ_DOCUMENT_V1, "Read this document.", image=data, mime=mime)
    doc_type = out.pop("doc_type", None)
    src = hint if hint in DOC_TYPES else (doc_type if doc_type in DOC_TYPES else "contract")
    return promise_from_model_output(out, src)
