"""Speech-to-text for dialect Bangla voice notes.

ASR_BACKEND=groq  -> Whisper large-v3 via Groq's free API (no install; 25 MB per file).
ASR_BACKEND=local -> the Bengali.AI regional Whisper-medium model (Apache-2.0):
https://huggingface.co/bengaliAI/tugstugi_bengaliai-regional-asr_whisper-medium
Install extras with: pip install -r requirements-asr.txt  (ffmpeg must be installed)
"""
from __future__ import annotations

import os
import tempfile
from functools import lru_cache

from . import config


@lru_cache(maxsize=1)
def _pipeline():
    import torch
    from transformers import pipeline

    device = 0 if torch.cuda.is_available() else -1
    return pipeline("automatic-speech-recognition", model=config.ASR_MODEL, device=device,
                    chunk_length_s=30)


def _groq(audio_bytes: bytes, suffix: str) -> dict:
    import httpx

    if not config.OPENAI_API_KEY:
        raise RuntimeError("ASR_BACKEND=groq needs OPENAI_API_KEY (your Groq key) in .env")
    if len(audio_bytes) > 25 * 1024 * 1024:
        raise RuntimeError("Voice note is larger than 25 MB; send a shorter one.")
    r = httpx.post(f"{config.OPENAI_BASE_URL}/audio/transcriptions",
                   headers={"Authorization": f"Bearer {config.OPENAI_API_KEY}"},
                   data={"model": config.ASR_GROQ_MODEL, "language": "bn", "temperature": "0",
                         "response_format": "json",
                         # Style hint: Whisper copies it, so numbers come out as digits and RL as letters
                         "prompt": "সৌদিতে ফ্যাক্টরির কাজ, বেতন ৩৫ হাজার টাকা। আমি মোট ৪ লাখ টাকা দিয়েছি। "
                                   "লাইসেন্স RL-9001। চুক্তিপত্র দেয়নি।"},
                   files={"file": (f"voice{suffix}", audio_bytes)}, timeout=120)
    if r.status_code >= 400:
        raise RuntimeError(f"Speech-to-text failed ({r.status_code}): {r.text[:200]}")
    return {"text": (r.json().get("text") or "").strip(), "model": f"groq:{config.ASR_GROQ_MODEL}"}


def transcribe(audio_bytes: bytes, suffix: str = ".ogg") -> dict:
    """Returns {"text": ..., "model": ...}. Raises RuntimeError when ASR is disabled or fails."""
    if not config.ASR_ENABLED:
        raise RuntimeError("ASR is disabled. Set ASR_ENABLED=true (see README) or send a transcript.")
    if config.ASR_BACKEND == "groq":
        return _groq(audio_bytes, suffix)
    # delete=False: Windows cannot reopen a temp file that is still open
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(audio_bytes)
        path = f.name
    try:
        out = _pipeline()(path, generate_kwargs={"language": "bengali", "task": "transcribe"})
    finally:
        os.remove(path)
    return {"text": out["text"].strip(), "model": config.ASR_MODEL}
