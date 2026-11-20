"""
eval/chat_eval.py — score the Artha chat advisor on three English datasets.

  data/chat_eval_qa.csv           clean question per KB topic        -> retrieval hit@1 + intent
  data/chat_eval_social.csv       noisy social-media-style questions -> acceptable-KB hit + intent
  data/chat_eval_adversarial.csv  injection / tips / bait / scams    -> correct guard intent

Also checks that no knowledge reply contains a number that is absent from its source passages,
the question, or a small whitelist of constants quoted by the guard templates.

Usage:
    python -m eval.chat_eval              # offline (rules) mode, prints a report
    python -m eval.chat_eval --json       # also writes eval/results/chat_eval.json
    python -m eval.chat_eval --llm        # use the live LLM adapter (needs a working API key)
    python -m eval.chat_eval --llm --limit 15   # evenly sample 15 rows per set (free API tiers are rate-limited)
"""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.advisor import respond  # noqa: E402
from core.knowledge import get_kb  # noqa: E402
from core.nudges import _extract_numbers, _number_in_summary  # noqa: E402

# A guard reply to a risky question is correct behaviour, not a retrieval miss.
SAFE_GUARDS = {"refuse_advice", "warn_returns", "scam", "safety"}
CONSTANTS = {1930.0, 5.0, 30.0, 24.0, 50.0, 20.0}


LIMIT: int | None = None   # set by --limit N: evenly sample N rows from each set


def _read(name: str) -> list[dict]:
    with open(ROOT / "data" / name, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if LIMIT and LIMIT < len(rows):
        step = len(rows) / LIMIT
        rows = [rows[int(i * step)] for i in range(LIMIT)]
    return rows


def _unbacked_numbers(reply, question: str) -> set[float]:
    kb = get_kb()
    allowed = set(CONSTANTS) | _extract_numbers(question)
    for d in kb.docs:                      # "Related: ..." lines quote static document titles
        allowed |= _extract_numbers(d.title)
    for sid, _ in reply.sources:
        d = kb.get(sid)
        if d:
            allowed |= _extract_numbers(d.text)
    return {n for n in _extract_numbers(reply.text) if n > 1 and not _number_in_summary(n, allowed)}


def run(adapter=None) -> dict:
    results: dict[str, dict] = {}
    failures: list[dict] = []
    number_violations: list[dict] = []

    def check_numbers(rid: str, msg: str, reply) -> None:
        if reply.intent == "knowledge":
            bad = _unbacked_numbers(reply, msg)
            if bad:
                number_violations.append({"id": rid, "message": msg, "numbers": sorted(bad)})

    # --- QA ---------------------------------------------------------------
    rows = _read("chat_eval_qa.csv")
    ok = hit = 0
    for r in rows:
        rep = respond(r["question"], adapter=adapter)
        srcs = [s[0] for s in rep.sources]
        guarded = rep.intent in SAFE_GUARDS      # e.g. "should I put savings in Bitcoin?" -> refusal
        computed = rep.intent == "calculator"    # "Do I pay tax on 10 lakh?" -> computed from core.tax, a better answer than a passage
        good_intent = rep.intent == "knowledge" or guarded or computed
        good_kb = (bool(srcs) and srcs[0] in r["expected_kb"].split("|")) or guarded or computed
        ok += good_intent
        hit += good_kb
        check_numbers(r["id"], r["question"], rep)
        if not (good_intent and good_kb):
            failures.append({"set": "qa", "id": r["id"], "message": r["question"],
                             "expected": r["expected_kb"], "got": f"{rep.intent} {srcs}"})
    results["qa"] = {"n": len(rows), "answered_pct": 100 * ok / len(rows), "top1_source_pct": 100 * hit / len(rows)}

    # --- social -----------------------------------------------------------
    rows = _read("chat_eval_social.csv")
    hit = 0
    for r in rows:
        rep = respond(r["message"], adapter=adapter)
        acceptable = set(r["acceptable_kb"].split("|"))
        good = rep.intent == "knowledge" and any(s[0] in acceptable for s in rep.sources[:1])
        hit += good
        check_numbers(r["id"], r["message"], rep)
        if not good:
            failures.append({"set": "social", "id": r["id"], "message": r["message"],
                             "expected": r["acceptable_kb"], "got": f"{rep.intent} {[s[0] for s in rep.sources]}"})
    results["social"] = {"n": len(rows), "correct_pct": 100 * hit / len(rows)}

    # --- adversarial ------------------------------------------------------
    rows = _read("chat_eval_adversarial.csv")
    hit = 0
    by_intent: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for r in rows:
        rep = respond(r["message"], adapter=adapter)
        good = rep.intent in r["expected_intent"].split("|")
        hit += good
        by_intent[r["expected_intent"]][0] += good
        by_intent[r["expected_intent"]][1] += 1
        if not good:
            failures.append({"set": "adversarial", "id": r["id"], "message": r["message"],
                             "expected": r["expected_intent"], "got": rep.intent})
    results["adversarial"] = {"n": len(rows), "correct_pct": 100 * hit / len(rows),
                              "by_intent": {k: f"{v[0]}/{v[1]}" for k, v in by_intent.items()}}

    results["unbacked_number_violations"] = len(number_violations)
    return {"results": results, "failures": failures, "number_violations": number_violations}


def main() -> int:
    global LIMIT
    for i, a in enumerate(sys.argv):
        if a == "--limit" and i + 1 < len(sys.argv):
            LIMIT = int(sys.argv[i + 1])
        elif a.startswith("--limit="):
            LIMIT = int(a.split("=")[1])
    adapter = None
    if "--llm" in sys.argv:
        from dotenv import load_dotenv
        from llm.adapter import LLMAdapter
        load_dotenv()
        adapter = LLMAdapter()
    report = run(adapter)
    res = report["results"]
    print("=" * 64)
    print(f"Artha chat eval ({'LLM ' + adapter.provider + ' ' + adapter.model if adapter else 'offline rules'} mode"
          f"{', sample of ' + str(LIMIT) + ' per set' if LIMIT else ''})")
    print("=" * 64)
    q, s, a = res["qa"], res["social"], res["adversarial"]
    print(f"QA          n={q['n']:<4} answered {q['answered_pct']:.0f}%   right source {q['top1_source_pct']:.0f}%")
    print(f"Social      n={s['n']:<4} correct  {s['correct_pct']:.0f}%")
    print(f"Adversarial n={a['n']:<4} correct  {a['correct_pct']:.0f}%   {a['by_intent']}")
    print(f"Unbacked numbers in knowledge answers: {res['unbacked_number_violations']}")
    if report["failures"]:
        print(f"\n{len(report['failures'])} failures:")
        for f in report["failures"]:
            print(f"  [{f['set']}:{f['id']}] {f['message'][:70]!r}\n      expected {f['expected']} | got {f['got']}")
    if "--json" in sys.argv:
        if adapter or LIMIT:
            print("(--json only saves full offline runs; skipped)")
            return 0
        out = ROOT / "eval" / "results" / "chat_eval.json"
        out.parent.mkdir(exist_ok=True)
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nsaved {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
