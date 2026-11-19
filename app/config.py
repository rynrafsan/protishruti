"""Settings from environment variables (see .env.example)."""
import os
from pathlib import Path

try:  # optional: load .env when python-dotenv is installed
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

ROOT = Path(__file__).resolve().parent.parent

# LLM provider: "mock" (offline, no key), "groq" / "openai" (any OpenAI-compatible API), "gemini" or "anthropic"
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "mock").split("#")[0].strip().lower()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5")
# OpenAI-compatible chat API. Defaults to Groq's free plan (no card needed); also works with
# OpenRouter (https://openrouter.ai/api/v1) or a local Ollama server (http://localhost:11434/v1).
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "qwen/qwen3.8-27b")
# Free tiers limit output tokens per minute (Groq: 1000 for qwen3.8-27b), so keep replies short
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "800"))


def _flag(name: str, default: bool) -> bool:
    v = os.getenv(name)
    return default if v is None or not v.strip() else v.split("#")[0].strip().lower() == "true"


# Which steps use the AI. On Groq's free tier only document reading does by default: the
# offline extractor and the Bangla template cover the other two without spending the quota.
LLM_EXTRACT = _flag("LLM_EXTRACT", LLM_PROVIDER not in ("groq", "openai"))
LLM_EXPLAIN = _flag("LLM_EXPLAIN", LLM_PROVIDER not in ("groq", "openai"))
LLM_EXTRACT_VOICE = _flag("LLM_EXTRACT_VOICE", True)  # speech-to-text output needs the AI to read numbers

# Speech-to-text (needs requirements-asr.txt and ideally a GPU)
ASR_ENABLED = _flag("ASR_ENABLED", False)
# "groq": Whisper large-v3 on Groq's free API (fast, nothing to install, works on Render too)
# "local": the Bengali.AI regional Whisper model on this computer (needs requirements-asr.txt)
ASR_BACKEND = (os.getenv("ASR_BACKEND") or ("groq" if LLM_PROVIDER == "groq" else "local")).split("#")[0].strip().lower()
ASR_GROQ_MODEL = os.getenv("ASR_GROQ_MODEL", "whisper-large-v3").split("#")[0].strip()
ASR_MODEL = os.getenv("ASR_MODEL", "bengaliAI/tugstugi_bengaliai-regional-asr_whisper-medium")

# Agency registry snapshot (CSV with license_no,name,status,valid_until)
AGENCY_CSV = os.getenv("AGENCY_CSV", str(ROOT / "data" / "agencies_sample.csv"))

RECORDS_DIR = Path(os.getenv("RECORDS_DIR", str(ROOT / "records")))
RECORDS_DIR.mkdir(parents=True, exist_ok=True)

# Safety: refuse real data on free tiers unless explicitly allowed
ALLOW_REAL_DATA = os.getenv("ALLOW_REAL_DATA", "false").lower() == "true"
# The WhatsApp number shown on the website (digits with country code, e.g. 8801XXXXXXXXX). Empty = pilot.
WA_DISPLAY_NUMBER = "".join(ch for ch in os.getenv("WA_DISPLAY_NUMBER", "").split("#")[0] if ch.isdigit())
