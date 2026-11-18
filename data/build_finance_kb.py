"""Build data/kb/KB022+.json and data/chat_eval_qa.csv from data/finance_kb/*.py.

Run:  python data/build_finance_kb.py
Single source of truth: edit the entries in data/finance_kb/, then rebuild.
"""
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from data.finance_kb import part1, part2, part3  # noqa: E402

PUBLISHER = ("Artha Kavach summary of public guidance (RBI / SEBI / IRDAI / Income Tax Dept) — "
             "pending manual verification")
BOOK_PUBLISHER = ("Artha Kavach original summary of a book's ideas (paraphrase, not a quotation; the author's "
                  "opinion, not settled fact) — pending manual verification")


def slug(title: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")
    return s[:40].strip("_")


def main() -> None:
    entries = part1.ENTRIES + part2.ENTRIES + part3.ENTRIES
    ids = [e["id"] for e in entries]
    assert len(ids) == len(set(ids)), "duplicate KB ids"
    kb_dir = ROOT / "data" / "kb"
    for old in kb_dir.glob("KB0[2-9]*_*.json"):
        if int(old.name[2:5]) >= 22:
            old.unlink()
    rows = []
    for e in entries:
        doc = {
            "id": e["id"], "title": e["title"],
            "publisher": BOOK_PUBLISHER if "book" in e["topics"] else PUBLISHER, "url": e["url"],
            "date_accessed": "2026-11-18", "topics": e["topics"], "text": e["text"],
            "summary_hinglish": e.get("hg", ""), "summary_hi": e.get("hi", ""), "aliases": e["aliases"],
            "verified": False,
        }
        (kb_dir / f"{e['id']}_{slug(e['title'])}.json").write_text(
            json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        for q in e["qs"]:
            lang, text = q.split(":", 1)
            if lang != "en":      # English-only scope for now (hg/hi kept in the source files)
                continue
            alt = ""
            if " ::" in text:
                text, alt = text.split(" ::", 1)
            rows.append({"id": f"qa{len(rows)+1:03d}", "lang": lang, "question": text,
                         "expected_kb": e["id"] + ("|" + alt if alt else "")})
    with open(ROOT / "data" / "chat_eval_qa.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id", "lang", "question", "expected_kb"])
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(entries)} KB docs and {len(rows)} eval questions")


if __name__ == "__main__":
    main()
