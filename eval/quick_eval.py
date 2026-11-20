"""
eval/quick_eval.py — Lightweight evaluation that needs only scikit-learn (no pandas).

Measures, on the held-out test split of data/scam_eval.csv:
  * rules baseline
  * ML classifier (word n-grams and word+char n-grams)
  * the offline pipeline (rules + classifier, no LLM)
and the SMS parser on data/sample_sms.csv.

Run:
  python -m eval.quick_eval            # print a table
  python -m eval.quick_eval --json     # also write eval/results/quick_eval.json
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scam.classifier import ScamClassifier, load_split  # noqa: E402
from scam.pipeline import analyse  # noqa: E402
from scam.rules import run_rules  # noqa: E402

LABELS = ["scam", "suspicious", "safe"]


def _deep_or(clf):
    """The app's pipeline uses the shipped deep model when present; evaluate the same thing."""
    try:
        from scam.deep_model import load_default
        return load_default() or clf
    except Exception:
        return clf
SCAM_CSV = ROOT / "data" / "scam_eval.csv"
SMS_CSV = ROOT / "data" / "sample_sms.csv"


def _f1_report(y_true: list[str], y_pred: list[str]) -> dict:
    out = {}
    for c in LABELS:
        tp = sum(t == c and p == c for t, p in zip(y_true, y_pred))
        fp = sum(t != c and p == c for t, p in zip(y_true, y_pred))
        fn = sum(t == c and p != c for t, p in zip(y_true, y_pred))
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        out[c] = {"precision": round(prec, 3), "recall": round(rec, 3), "f1": round(f1, 3)}
    out["macro_f1"] = round(sum(out[c]["f1"] for c in LABELS) / len(LABELS), 3)
    out["accuracy"] = round(sum(t == p for t, p in zip(y_true, y_pred)) / max(len(y_true), 1), 3)
    out["safe_flagged"] = sum(t == "safe" and p != "safe" for t, p in zip(y_true, y_pred))
    return out


def rules_verdict(text: str) -> str:
    s = run_rules(text).score
    return "scam" if s >= 0.55 else "suspicious" if s >= 0.25 else "safe"


def eval_scam() -> dict:
    test = load_split(SCAM_CSV, "test")
    y = [r["label"] for r in test]
    hl = [i for i, r in enumerate(test) if r["hinglish"]]
    results = {"n_test": len(test), "n_hinglish": len(hl)}

    preds = {"rules": [rules_verdict(r["text"]) for r in test]}
    for feats in ("word", "word+char"):
        clf = ScamClassifier(features=feats)
        clf.train(SCAM_CSV)
        preds[f"clf_{feats}"] = [clf.predict(r["text"]) for r in test]
        if feats == "word+char":
            preds["pipeline_offline"] = [analyse(r["text"], classifier=_deep_or(clf)).verdict for r in test]

    for name, p in preds.items():
        results[name] = _f1_report(y, p)
        results[name]["hinglish_macro_f1"] = (
            _f1_report([y[i] for i in hl], [p[i] for i in hl])["macro_f1"] if hl else None
        )
    return results


def eval_parser() -> dict:
    from core.parser import parse_message

    rows = list(csv.DictReader(open(SMS_CSV, encoding="utf-8")))
    parseable = [r for r in rows if r["parseable"] == "true"]
    ok = amount_ok = type_ok = 0
    false_pos = 0
    for r in rows:
        p = parse_message(r["raw_sms"])
        if r["parseable"] != "true":
            false_pos += p.parse_method != "failed"
            continue
        if p.parse_method == "failed":
            continue
        ok += 1
        amount_ok += abs((p.amount or 0) - float(r["expected_amount"] or 0)) < 0.01
        type_ok += p.transaction_type == r["expected_type"]
    return {
        "n_messages": len(rows),
        "n_parseable": len(parseable),
        "regex_success_rate": round(ok / len(parseable), 3),
        "amount_accuracy_on_parsed": round(amount_ok / max(ok, 1), 3),
        "type_accuracy_on_parsed": round(type_ok / max(ok, 1), 3),
        "non_transactions_wrongly_parsed": false_pos,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="write eval/results/quick_eval.json")
    args = ap.parse_args()

    scam = eval_scam()
    parser = eval_parser()

    print(f"Scam detection - {scam['n_test']} test messages ({scam['n_hinglish']} Hinglish)")
    print(f"{'detector':<20}{'macroF1':>8}{'scamF1':>8}{'suspF1':>8}{'safeF1':>8}{'hinglish':>10}{'safe->flag':>10}")
    for k in ("rules", "clf_word", "clf_word+char", "pipeline_offline"):
        r = scam[k]
        print(f"{k:<20}{r['macro_f1']:>8}{r['scam']['f1']:>8}{r['suspicious']['f1']:>8}"
              f"{r['safe']['f1']:>8}{str(r['hinglish_macro_f1']):>10}{r['safe_flagged']:>10}")
    print()
    print("SMS parser (regex only):", json.dumps(parser))

    if args.json:
        out = ROOT / "eval" / "results" / "quick_eval.json"
        out.write_text(json.dumps({"scam": scam, "parser": parser}, indent=2), encoding="utf-8")
        print(f"\nSaved {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
