"""Check that your AI provider answers, and how fast.

    python tools/llm_ping.py            # one tiny call with the provider/model in .env
    python tools/llm_ping.py --list     # Gemini only: list the models your key can use

Run it from the project folder with the environment active.
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import config, llm  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="list Gemini models that can generate text")
    ap.add_argument("--model", help="try this model instead of the one in .env")
    a = ap.parse_args()

    if a.list:
        from google import genai
        client = genai.Client(api_key=config.GEMINI_API_KEY)
        for m in client.models.list():
            actions = getattr(m, "supported_actions", None) or []
            if not actions or "generateContent" in actions:
                print(m.name.replace("models/", ""))
        return

    if a.model:
        if config.LLM_PROVIDER == "gemini":
            config.GEMINI_MODEL = a.model
        elif config.LLM_PROVIDER == "anthropic":
            config.ANTHROPIC_MODEL = a.model
        else:
            config.OPENAI_MODEL = a.model
    model = {"gemini": config.GEMINI_MODEL, "anthropic": config.ANTHROPIC_MODEL}.get(
        config.LLM_PROVIDER, config.OPENAI_MODEL)
    print(f"Provider: {config.LLM_PROVIDER}   model: {model}   timeout: {llm.TIMEOUT_S}s")
    if config.LLM_PROVIDER == "mock":
        print("LLM_PROVIDER is mock: set gemini, groq or anthropic in .env first.")
        return
    t = time.perf_counter()
    try:
        out = llm.call("Reply with a JSON object.", 'Return {"ok": true}.')
        print(f"OK in {time.perf_counter() - t:.1f}s: {out}")
    except Exception as e:
        print(f"FAILED after {time.perf_counter() - t:.1f}s: {type(e).__name__}: {str(e)[:300]}")


if __name__ == "__main__":
    main()
