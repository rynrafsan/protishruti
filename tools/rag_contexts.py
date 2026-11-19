"""Write an AI context line for every knowledge-base chunk (Anthropic-style contextual retrieval).

python tools/rag_contexts.py

For each chunk, the LLM in .env (Groq by default) reads the whole document and writes one short
sentence that situates the chunk (what it is about, key terms in Bangla and English). The
sentences are saved to data/knowledge/contexts.json and prepended to each chunk at index time,
which helps short or vague chunks match the right questions. Re-run after editing the knowledge base.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import config, llm, rag  # noqa: E402

PROMPT = """<document>
{doc}
</document>
Here is the chunk we want to situate within the whole document:
<chunk>
{chunk}
</chunk>
Give one short sentence (max 30 words) that situates this chunk within the document to improve search retrieval: what it is about and its key terms, in Bangla with English keywords. Answer only with the sentence."""


def main():
    if config.LLM_PROVIDER == "mock":
        print("LLM_PROVIDER is mock: set groq (or gemini/anthropic) in .env first.")
        return
    config.LLM_MAX_TOKENS = 120  # one sentence; keeps us inside free-tier token limits
    docs = {p.stem: p.read_text(encoding="utf-8") for p in sorted(rag.KB_DIR.glob("*.md"))}
    ctx = json.loads(rag.CONTEXTS_FILE.read_text(encoding="utf-8")) if rag.CONTEXTS_FILE.exists() else {}
    rag.get_index.cache_clear()
    chunks = rag.get_index().chunks
    for i, c in enumerate(chunks, 1):
        if ctx.get(c.id):
            continue
        doc = docs[c.id.split("#")[0]]
        for attempt in range(3):
            try:
                ctx[c.id] = llm.call("You write retrieval context.", PROMPT.format(doc=doc, chunk=c.text),
                                     want_json=False).strip().splitlines()[0][:300]
                break
            except Exception as e:
                print(f"  retry {c.id}: {str(e)[:80]}")
                time.sleep(20)
        print(f"[{i}/{len(chunks)}] {c.id}: {ctx.get(c.id, '(failed)')[:70]}")
        rag.CONTEXTS_FILE.write_text(json.dumps(ctx, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Saved {len(ctx)} contexts to {rag.CONTEXTS_FILE}. Now run: python tools/rag_eval.py")


if __name__ == "__main__":
    main()
