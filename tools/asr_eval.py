"""Measure speech-to-text word error rate (WER) per dialect.

Input CSV columns: path,reference,dialect   (reference = correct transcript)
pip install -r requirements-asr.txt jiwer
ASR_ENABLED=true python tools/asr_eval.py --csv data/voice_test.csv
Report every dialect, including the weak ones.
"""
import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main():
    import jiwer
    from app import asr

    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    a = ap.parse_args()
    refs, hyps = defaultdict(list), defaultdict(list)
    with open(a.csv, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            audio = Path(row["path"])
            text = asr.transcribe(audio.read_bytes(), suffix=audio.suffix)["text"]
            refs[row["dialect"]].append(row["reference"])
            hyps[row["dialect"]].append(text)
    print(f"{'dialect':<16}{'n':>4}  WER")
    all_r, all_h = [], []
    for d in sorted(refs):
        print(f"{d:<16}{len(refs[d]):>4}  {jiwer.wer(refs[d], hyps[d]):.3f}")
        all_r += refs[d]
        all_h += hyps[d]
    print(f"{'ALL':<16}{len(all_r):>4}  {jiwer.wer(all_r, all_h):.3f}")


if __name__ == "__main__":
    main()
