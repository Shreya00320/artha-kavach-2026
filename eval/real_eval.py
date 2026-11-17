"""
eval/real_eval.py — Score Scam Shield on REAL messages you collected.

Input CSV (UTF-8) with columns:
  text   — the message exactly as received (remove personal names/numbers if you like)
  label  — scam | suspicious | safe   (your honest judgement; leave empty to only get predictions)

Run:
  python -m eval.real_eval data/real_sms.csv            # offline: rules + ML classifier
  python -m eval.real_eval data/real_sms.csv --llm      # + LLM judge (needs API key in .env)

Writes eval/results/real_eval.json and eval/results/real_predictions.csv.
Keep the real messages out of git if they contain personal data (data/private/ is git-ignored).
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from eval.quick_eval import _f1_report, rules_verdict, SCAM_CSV  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv_path")
    ap.add_argument("--llm", action="store_true", help="also run the LLM judge (needs API key)")
    args = ap.parse_args()

    rows = [r for r in csv.DictReader(open(args.csv_path, encoding="utf-8-sig")) if (r.get("text") or "").strip()]
    if not rows:
        sys.exit("No rows with a 'text' column found.")

    from scam.classifier import ScamClassifier
    from scam.pipeline import analyse

    clf = ScamClassifier()
    clf.train(SCAM_CSV)

    adapter = None
    if args.llm:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
        from llm.adapter import LLMAdapter
        adapter = LLMAdapter()

    out = []
    for r in rows:
        text = r["text"].strip()
        res = analyse(text, adapter=adapter, classifier=clf)
        out.append({
            "text": text,
            "label": (r.get("label") or "").strip().lower(),
            "rules": rules_verdict(text),
            "ml": clf.predict(text),
            "final": res.verdict,
            "llm_used": res.llm_used,
            "top_red_flag": res.red_flags[0].flag if res.red_flags else "",
        })

    labelled = [o for o in out if o["label"] in ("scam", "suspicious", "safe")]
    report = {"n_messages": len(out), "n_labelled": len(labelled), "llm": bool(adapter)}
    if labelled:
        y = [o["label"] for o in labelled]
        for det in ("rules", "ml", "final"):
            report[det] = _f1_report(y, [o[det] for o in labelled])
        # The number judges care about most: scams caught, safe messages wrongly flagged
        report["scams_caught"] = f"{sum(o['label'] == 'scam' and o['final'] == 'scam' for o in labelled)}" \
                                 f"/{sum(o['label'] == 'scam' for o in labelled)}"
        report["safe_wrongly_flagged"] = f"{sum(o['label'] == 'safe' and o['final'] != 'safe' for o in labelled)}" \
                                         f"/{sum(o['label'] == 'safe' for o in labelled)}"

    res_dir = ROOT / "eval" / "results"
    res_dir.mkdir(parents=True, exist_ok=True)
    (res_dir / "real_eval.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    with open(res_dir / "real_predictions.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)

    print(f"Messages: {report['n_messages']} ({report['n_labelled']} labelled) · LLM: {report['llm']}")
    if labelled:
        print(f"{'detector':<8}{'macroF1':>9}{'accuracy':>10}")
        for det in ("rules", "ml", "final"):
            print(f"{det:<8}{report[det]['macro_f1']:>9}{report[det]['accuracy']:>10}")
        print(f"Scams caught: {report['scams_caught']} · Safe wrongly flagged: {report['safe_wrongly_flagged']}")
    print("Saved eval/results/real_eval.json and real_predictions.csv")


if __name__ == "__main__":
    main()
