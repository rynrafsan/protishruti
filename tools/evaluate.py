"""Benchmark the pipeline on synthetic cases: does each planted rule get flagged?

python tools/generate first, then:
python tools/evaluate.py --dir data/synthetic            # rules only (ground-truth fields)
python tools/evaluate.py --dir data/synthetic --extract  # transcript -> extractor -> rules
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import extract, rules  # noqa: E402
from app.schema import Promise  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="data/synthetic")
    ap.add_argument("--extract", action="store_true", help="use the extractor on transcripts")
    a = ap.parse_args()
    hits, totals, false_alarms = Counter(), Counter(), 0
    for case in sorted(Path(a.dir).glob("case_*")):
        planted = json.loads((case / "label.json").read_text())["planted_rule"]
        if a.extract:
            promise = extract.extract_promise((case / "transcript_bn.txt").read_text(encoding="utf-8"))
        else:
            promise = Promise.model_validate(json.loads((case / "promise.json").read_text(encoding="utf-8")))
        docs = [Promise.model_validate(json.loads(p.read_text(encoding="utf-8")))
                for p in (case / "visa.json", case / "contract.json") if p.exists()]
        flags = rules.run_rules(promise, docs)
        ids = {f.rule_id for f in flags if f.severity != "info"}
        totals[planted] += 1
        if planted == "NONE":
            false_alarms += bool(ids - {"R09"})
        elif planted in ids:
            hits[planted] += 1
    print("rule  recall")
    for r in sorted(totals):
        if r != "NONE":
            print(f"{r}   {hits[r]}/{totals[r]}")
    print(f"clean cases with a false alarm: {false_alarms}/{totals['NONE']}")
    print(f"(evaluated on {date.today()})")


if __name__ == "__main__":
    main()
