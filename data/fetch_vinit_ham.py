"""Extract clean English ORDINARY-text examples from a third-party dataset for the scam classifier.

Source : https://github.com/vinit9638/SMS-scam-detection-dataset  (138,813 rows, ham/spam, no licence stated)
Used   : only the `ham` rows, as `safe` training examples, written to data/external/ (git-ignored).
NOT used: the `spam` rows — profiling showed they are noisy (tweets, blog and link spam, non-English).

Cleaning: English-looking ASCII only, 15-250 chars, de-duplicated, and every message that also appears in any
of our TEST sets is removed (the dataset contains the UCI SMS Spam Collection, so our UCI test split would
otherwise leak into training).

Usage:
    curl -sSL -o ds.csv https://raw.githubusercontent.com/vinit9638/SMS-scam-detection-dataset/main/sms_scam_detection_dataset_merged_with_lang.csv
    python -I data/fetch_vinit_ham.py path/to/ds.csv

The file is treated as untrusted data: read with the csv module only, never executed.
"""
import csv
import random
import re
import sys
from pathlib import Path

DATA = Path(__file__).resolve().parent
OUT = DATA / "external"
COMMON = {"the", "and", "you", "is", "to", "a", "i", "it", "in", "of", "for", "my", "me", "we", "are", "on", "that",
          "this", "have", "be", "with", "at", "not", "can", "will", "do", "your", "so", "but", "what", "u", "ur"}


def norm(t: str) -> str:
    return " ".join(t.lower().split())


def test_texts() -> set:
    """Everything we evaluate on — must never be trained on."""
    out = set()
    for name, split in (("external/sms_ham_test.csv", None), ("ordinary_text_eval.csv", None),
                        ("scam_heldout.csv", None), ("scam_eval.csv", "test")):
        p = DATA / name
        if p.exists():
            for r in csv.DictReader(open(p, encoding="utf-8")):
                if split is None or r.get("split") == split:
                    out.add(norm(r["text"]))
    return out


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    csv.field_size_limit(10 ** 7)
    banned = test_texts() | {norm(r["text"]) for r in csv.DictReader(open(DATA / "external" / "sms_ham_train.csv", encoding="utf-8"))}
    seen, keep = set(), []
    stats = {"rows": 0, "ham": 0, "non_ascii_or_len": 0, "not_english": 0, "overlap": 0, "dup": 0}
    for r in csv.DictReader(open(sys.argv[1], encoding="utf-8", errors="replace", newline="")):
        stats["rows"] += 1
        if r.get("label") != "ham":
            continue
        stats["ham"] += 1
        t = " ".join((r.get("text") or "").split())
        t = t.replace("&lt;#&gt;", "").replace("&lt;DECIMAL&gt;", "").replace("&amp;", "&").strip()
        if not (15 <= len(t) <= 250) or not t.isascii():
            stats["non_ascii_or_len"] += 1
            continue
        words = set(re.findall(r"[a-z']+", t.lower()))
        if len(words & COMMON) < 2:
            stats["not_english"] += 1
            continue
        n = norm(t)
        if n in banned:
            stats["overlap"] += 1
            continue
        if n in seen:
            stats["dup"] += 1
            continue
        seen.add(n)
        keep.append(t)
    random.Random(5).shuffle(keep)
    keep = keep[:3000]
    OUT.mkdir(exist_ok=True)
    with open(OUT / "vinit_ham_train.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "label", "text", "language", "hinglish", "split", "notes"])
        for i, t in enumerate(keep, 1):
            w.writerow([f"VH{i:04d}", "safe", t, "en", "false", "train", "vinit9638-ham"])
    print(stats, "-> kept", len(keep))


if __name__ == "__main__":
    main()
