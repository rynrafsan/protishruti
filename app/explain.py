"""Plain-Bangla explanation of flags. The LLM only explains; it never adds flags."""
from __future__ import annotations

import json

from . import config, llm, prompts
from .schema import Flag

NEXT_STEPS = [
    "টাকা দেওয়ার আগে লিখিত ও স্বাক্ষরিত চুক্তিপত্র চান।",
    "এজেন্সির লাইসেন্স (RL) নম্বর সরকারি তালিকায় মিলিয়ে নিন।",
    "সন্দেহ হলে প্রবাসী কল্যাণ হেল্পলাইন বা কোনো অভিবাসী অধিকার সংস্থার সাথে যোগাযোগ করুন।",
]


def template_explanation(flags: list[Flag], not_checked: list[str]) -> str:
    lines: list[str] = []
    if not flags:
        lines.append("আপনি যা দেখিয়েছেন তাতে কোনো অমিল পাওয়া যায়নি। এর মানে এই নয় যে চাকরিটি নিরাপদ।")
    for f in flags:
        line = f"• {f.title_bn}।"
        if f.promised:
            line += f" প্রতিশ্রুতি: {f.promised}।"
        if f.found:
            line += f" পাওয়া গেছে: {f.found}।"
        line += f" (সূত্র: {f.source})"
        lines.append(line)
    lines.append("\nযা যাচাই করা হয়নি: " + "; ".join(not_checked))
    lines.append("\nআপনার করণীয়:\n" + "\n".join(f"{i+1}. {s}" for i, s in enumerate(NEXT_STEPS)))
    lines.append("\n(এটি আইনি তথ্য, আইনি পরামর্শ নয়।)")
    return "\n".join(lines)


def explain(flags: list[Flag], not_checked: list[str]) -> str:
    if config.LLM_PROVIDER == "mock" or not config.LLM_EXPLAIN:
        return template_explanation(flags, not_checked)
    payload = json.dumps({"flags": [f.model_dump() for f in flags], "not_checked": not_checked},
                         ensure_ascii=False)
    try:
        return llm.call(prompts.EXPLAIN_FLAGS_V1, payload, want_json=False).strip()
    except Exception:
        return template_explanation(flags, not_checked)  # never leave the worker without an answer
