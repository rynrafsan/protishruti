"""Thin wrapper over LLM providers. Every call returns parsed JSON or plain text.

LLM_PROVIDER=mock    -> offline heuristics, no API key (default; good for tests and demos)
LLM_PROVIDER=gemini  -> Google Gemini via google-genai
LLM_PROVIDER=anthropic -> Claude via anthropic SDK
LLM_PROVIDER=groq|openai -> any OpenAI-compatible chat API (Groq free plan by default,
                          OpenRouter, or a local Ollama server)
"""
from __future__ import annotations

import base64
import json
import os
import re
import time
from typing import Optional

from . import config


class LLMError(RuntimeError):
    pass


TIMEOUT_S = int(os.getenv("LLM_TIMEOUT_S", "90"))  # per model call
COOLDOWN_S = 120  # after a timeout/5xx, skip the provider for this long instead of waiting again
_down_until = 0.0


def _is_outage(e: Exception) -> bool:
    s = f"{type(e).__name__} {e}".lower()
    return any(k in s for k in ("timeout", "timed out", "deadline", " 500", " 502", " 503", " 504",
                                "unavailable", "overloaded", "servererror"))


def _parse_json(text: str) -> dict:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()  # reasoning models
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise LLMError(f"Model did not return JSON: {text[:200]}")
    return json.loads(m.group(0))


def _gemini(system: str, prompt: str, image: Optional[bytes], mime: Optional[str], want_json: bool) -> str:
    from google import genai
    from google.genai import types

    try:  # fail after 60 s instead of hanging, and don't retry for minutes on quota errors
        http = types.HttpOptions(timeout=TIMEOUT_S * 1000, retry_options=types.HttpRetryOptions(attempts=1))
    except (AttributeError, TypeError):  # older google-genai
        http = types.HttpOptions(timeout=TIMEOUT_S * 1000)
    client = genai.Client(api_key=config.GEMINI_API_KEY, http_options=http)
    contents: list = []
    if image:
        contents.append(types.Part.from_bytes(data=image, mime_type=mime or "image/jpeg"))
    contents.append(prompt)
    base = dict(system_instruction=system, temperature=0,
                response_mime_type="application/json" if want_json else "text/plain")
    try:  # low thinking = much faster; reading a form needs little reasoning
        cfg = types.GenerateContentConfig(**base, thinking_config=types.ThinkingConfig(thinking_level="low"))
        resp = client.models.generate_content(model=config.GEMINI_MODEL, contents=contents, config=cfg)
    except Exception as e:
        if "think" not in str(e).lower():
            raise
        resp = client.models.generate_content(model=config.GEMINI_MODEL, contents=contents,
                                              config=types.GenerateContentConfig(**base))
    return resp.text or ""


def _anthropic(system: str, prompt: str, image: Optional[bytes], mime: Optional[str], want_json: bool) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY, timeout=TIMEOUT_S, max_retries=0)
    content: list = []
    if image:
        content.append({"type": "image", "source": {"type": "base64", "media_type": mime or "image/jpeg",
                                                     "data": base64.b64encode(image).decode()}})
    content.append({"type": "text", "text": prompt + ("\nRespond with JSON only." if want_json else "")})
    msg = client.messages.create(model=config.ANTHROPIC_MODEL, max_tokens=2000, temperature=0,
                                 system=system, messages=[{"role": "user", "content": content}])
    return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")


def _openai_compatible(system: str, prompt: str, image: Optional[bytes], mime: Optional[str],
                       want_json: bool, max_tokens: Optional[int] = None, timeout: Optional[float] = None,
                       wait_on_quota: bool = True) -> str:
    import httpx

    if not config.OPENAI_API_KEY and "localhost" not in config.OPENAI_BASE_URL:
        raise LLMError("OPENAI_API_KEY is empty: put your Groq (or other) key in .env")
    content: list = []
    if image:
        url = f"data:{mime or 'image/jpeg'};base64,{base64.b64encode(image).decode()}"
        content.append({"type": "image_url", "image_url": {"url": url}})
    content.append({"type": "text", "text": prompt + ("\nRespond with JSON only." if want_json else "")})
    timeout = timeout or TIMEOUT_S
    body = {"model": config.OPENAI_MODEL, "temperature": 0, "max_tokens": max_tokens or config.LLM_MAX_TOKENS,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": content}]}
    if "groq.com" in config.OPENAI_BASE_URL:
        body["reasoning_effort"] = "none"  # no hidden "thinking": faster, and it doesn't eat the token quota
    if want_json:
        body["response_format"] = {"type": "json_object"}
    headers = {"Authorization": f"Bearer {config.OPENAI_API_KEY}"}
    url = f"{config.OPENAI_BASE_URL}/chat/completions"
    r = httpx.post(url, json=body, headers=headers, timeout=timeout)
    # Options a model may not support: drop them one at a time and retry.
    for opt in ("reasoning_effort", "response_format"):
        if r.status_code == 400 and opt in body:
            body.pop(opt)
            r = httpx.post(url, json=body, headers=headers, timeout=timeout)
    if r.status_code == 429 and wait_on_quota:  # per-minute quota: wait once, as the server asks (max 30 s)
        try:
            wait = float(r.headers.get("retry-after", "10"))
        except ValueError:
            wait = 10.0
        if wait <= 30:
            time.sleep(wait)
            r = httpx.post(url, json=body, headers=headers, timeout=timeout)
    if r.status_code >= 400:
        raise LLMError(f"{r.status_code} from {config.OPENAI_BASE_URL}: {r.text[:300]}")
    return r.json()["choices"][0]["message"].get("content") or ""


def call(system: str, prompt: str, image: Optional[bytes] = None, mime: Optional[str] = None,
         want_json: bool = True, **opts):
    """opts (OpenAI-compatible providers only): max_tokens, timeout, wait_on_quota=False to fail fast
    on a 429 so a caller with a fallback (the rights Q&A) answers at once instead of waiting."""
    global _down_until
    provider = config.LLM_PROVIDER
    fn = {"gemini": _gemini, "anthropic": _anthropic, "groq": _openai_compatible,
          "openai": _openai_compatible}.get(provider)
    if fn is None:
        raise LLMError("mock provider has no generic call; use the module-specific fallbacks")
    if time.time() < _down_until:  # the provider just timed out: fail fast, the caller falls back
        raise LLMError(f"{provider} skipped: it timed out or was unavailable less than {COOLDOWN_S}s ago")
    try:
        text = fn(system, prompt, image, mime, want_json, **opts) if fn is _openai_compatible \
            else fn(system, prompt, image, mime, want_json)
    except Exception as e:
        if _is_outage(e):
            _down_until = time.time() + COOLDOWN_S
        raise
    return _parse_json(text) if want_json else text
