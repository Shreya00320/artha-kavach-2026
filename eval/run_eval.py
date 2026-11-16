"""eval/run_eval.py – Artha Kavach evaluation suite.

Produces four result sections:
  1. Scam detection  — precision / recall / F1 / confusion matrix for
                       (a) Rules baseline, (b) ML classifier, (c) combined pipeline.
                       Hinglish subset reported separately.
  2. Parser accuracy — regex-only vs regex+LLM parse success rate on sample_sms.csv.
  3. Budget engine   — invariant checks (totals, 50/30/20 math, pace, nudge number-check).
  4. Failure cases   — 3 real failure examples with explanation.

All results printed to stdout and saved to eval/results/.
Requires: pandas, scikit-learn, matplotlib already installed.
LLM calls are SKIPPED by default (--llm flag to enable, costs API quota).

Usage:
  cd C:\\Users\\DELL\\Documents\\AI-FINANCE
  .venv\\Scripts\\python.exe eval/run_eval.py          # offline (rules + ML only)
  .venv\\Scripts\\python.exe eval/run_eval.py --llm    # + LLM judge (needs GEMINI_API_KEY)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import textwrap
from pathlib import Path

# Fix matplotlib config dir before any import of matplotlib (avoids permission
# warnings on systems where AppData\Local\matplotlib is not writable).
os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).parent.parent / ".cache" / "mpl"))

import pandas as pd
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT    = Path(__file__).parent.parent
RESULTS = ROOT / "eval" / "results"
RESULTS.mkdir(parents=True, exist_ok=True)

SCAM_EVAL_CSV  = ROOT / "data" / "scam_eval.csv"
SAMPLE_SMS_CSV = ROOT / "data" / "sample_sms.csv"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _header(title: str) -> None:
    bar = "=" * 68
    print(f"\n{bar}")
    print(f"  {title}")
    print(bar)


def _subheader(title: str) -> None:
    print(f"\n--- {title} ---")


def _metrics_table(y_true, y_pred, labels=("scam", "suspicious", "safe")) -> dict:
    """Return per-class and macro precision/recall/F1."""
    from sklearn.metrics import classification_report, confusion_matrix
    report = classification_report(
        y_true, y_pred, labels=list(labels),
        output_dict=True, zero_division=0,
    )
    cm = confusion_matrix(y_true, y_pred, labels=list(labels))
    return {"report": report, "confusion_matrix": cm.tolist(), "labels": list(labels)}


def _print_report(metrics: dict) -> None:
    report = metrics["report"]
    labels = metrics["labels"]
    print(f"\n{'':>14}  {'P':>6}  {'R':>6}  {'F1':>6}  {'Supp':>6}")
    for lbl in labels:
        r = report.get(lbl, {})
        print(
            f"  {lbl:>12}  {r.get('precision',0):6.3f}  "
            f"{r.get('recall',0):6.3f}  {r.get('f1-score',0):6.3f}  "
            f"{int(r.get('support',0)):6d}"
        )
    mac = report.get("macro avg", {})
    print(
        f"\n  {'macro avg':>12}  {mac.get('precision',0):6.3f}  "
        f"{mac.get('recall',0):6.3f}  {mac.get('f1-score',0):6.3f}"
    )
    # Confusion matrix
    print(f"\n  Confusion matrix (rows=true, cols=pred) [{', '.join(labels)}]:")
    for row in metrics["confusion_matrix"]:
        print("    " + "  ".join(f"{v:4d}" for v in row))


def _save_json(name: str, data) -> None:
    path = RESULTS / f"{name}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"  → Saved {path.relative_to(ROOT)}")


# ---------------------------------------------------------------------------
# 1. Scam detection evaluation
# ---------------------------------------------------------------------------

def eval_scam(use_llm: bool = False) -> dict:
    _header("1. SCAM DETECTION EVALUATION")

    df = pd.read_csv(SCAM_EVAL_CSV)
    test_df = df[df["split"] == "test"].copy()
    hinglish_df = test_df[test_df["hinglish"] == True].copy()

    print(f"  Test set : {len(test_df)} messages")
    print(f"  Hinglish : {len(hinglish_df)} messages")
    print(f"  Label dist: {test_df['label'].value_counts().to_dict()}")

    # --- (a) Rules baseline ---
    _subheader("(a) Rules engine baseline")
    from scam.rules import run_rules

    def _rules_verdict(text: str) -> str:
        r = run_rules(text)
        if r.score >= 0.55:
            return "scam"
        elif r.score >= 0.25:
            return "suspicious"
        return "safe"

    test_df["pred_rules"] = test_df["text"].apply(_rules_verdict)
    rules_metrics = _metrics_table(test_df["label"], test_df["pred_rules"])
    _print_report(rules_metrics)

    # Hinglish subset
    if len(hinglish_df) > 0:
        hinglish_df["pred_rules"] = hinglish_df["text"].apply(_rules_verdict)
        hl_rules = _metrics_table(hinglish_df["label"], hinglish_df["pred_rules"])
        _subheader("(a-h) Rules — Hinglish subset")
        _print_report(hl_rules)
    else:
        hl_rules = {}

    # --- (b) ML Classifier ---
    _subheader("(b) ML Classifier (TF-IDF + LogReg)")
    from scam.classifier import ScamClassifier

    train_df = df[df["split"] == "train"]
    clf = ScamClassifier()
    clf.train(SCAM_EVAL_CSV)

    test_df["pred_clf"] = test_df["text"].apply(clf.predict)
    clf_metrics = _metrics_table(test_df["label"], test_df["pred_clf"])
    _print_report(clf_metrics)

    if len(hinglish_df) > 0:
        hinglish_df["pred_clf"] = hinglish_df["text"].apply(clf.predict)
        hl_clf = _metrics_table(hinglish_df["label"], hinglish_df["pred_clf"])
        _subheader("(b-h) Classifier — Hinglish subset")
        _print_report(hl_clf)
    else:
        hl_clf = {}

    # --- (c) Combined pipeline (rules + classifier, no LLM unless flag) ---
    pipeline_label = "(c) Combined pipeline (rules + ML" + (" + LLM)" if use_llm else ", offline)")
    _subheader(pipeline_label)

    adapter = None
    if use_llm:
        try:
            from llm.adapter import LLMAdapter
            adapter = LLMAdapter()
            print("  LLM adapter: live")
        except Exception as e:
            print(f"  LLM adapter failed ({e}); running offline.")

    from scam.pipeline import analyse

    def _pipeline_verdict(text: str) -> str:
        result = analyse(text, adapter=adapter, classifier=clf)
        return result.verdict

    print("  Running pipeline on test set (this may take a moment)…")
    test_df["pred_pipeline"] = test_df["text"].apply(_pipeline_verdict)
    pipeline_metrics = _metrics_table(test_df["label"], test_df["pred_pipeline"])
    _print_report(pipeline_metrics)

    if len(hinglish_df) > 0:
        hinglish_df["pred_pipeline"] = hinglish_df["text"].apply(_pipeline_verdict)
        hl_pipeline = _metrics_table(hinglish_df["label"], hinglish_df["pred_pipeline"])
        _subheader("(c-h) Pipeline — Hinglish subset")
        _print_report(hl_pipeline)
    else:
        hl_pipeline = {}

    # --- Comparison summary ---
    _subheader("Summary — macro F1 comparison")
    for name, m in [
        ("Rules baseline",  rules_metrics),
        ("ML Classifier",   clf_metrics),
        ("Combined pipeline", pipeline_metrics),
    ]:
        f1 = m["report"].get("macro avg", {}).get("f1-score", 0)
        print(f"  {name:<22} macro-F1 = {f1:.3f}")

    # Save predictions CSV for inspection
    pred_cols = ["id", "label", "text", "language", "hinglish",
                 "pred_rules", "pred_clf", "pred_pipeline"]
    test_df[pred_cols].to_csv(RESULTS / "scam_predictions.csv", index=False)
    print(f"\n  → Saved eval/results/scam_predictions.csv")

    results = {
        "rules":    rules_metrics,
        "clf":      clf_metrics,
        "pipeline": pipeline_metrics,
        "hinglish": {
            "rules":    hl_rules,
            "clf":      hl_clf,
            "pipeline": hl_pipeline,
        },
        "n_test":          len(test_df),
        "n_test_hinglish": len(hinglish_df),
        "llm_used":        use_llm and adapter is not None,
        "limitations": (
            "Small synthetic test set (47 examples). "
            "Hinglish subset has only 5 examples — treat those numbers as directional only. "
            "Model trained and tested on synthetic data; real-world performance may differ."
        ),
    }
    _save_json("scam_eval", results)
    return results


# ---------------------------------------------------------------------------
# 2. Parser accuracy evaluation
# ---------------------------------------------------------------------------

def eval_parser() -> dict:
    _header("2. PARSER ACCURACY (regex vs regex+LLM fallback)")

    df = pd.read_csv(SAMPLE_SMS_CSV)
    messages = df["raw_sms"].tolist()
    expected_parseable = df["parseable"].tolist()

    print(f"  Total messages : {len(messages)}")
    print(f"  Expected parseable: {sum(expected_parseable)} / {len(messages)}")

    from core.parser import parse_messages, parse_message

    # Regex-only (no adapter)
    print("\n  Running regex-only parser…")
    parsed_regex = parse_messages(messages, adapter=None)

    n_regex_ok     = sum(1 for p in parsed_regex if p.parse_method == "regex")
    n_llm_ok       = 0   # no LLM in this pass
    n_failed_regex = sum(1 for p in parsed_regex if p.parse_method == "failed")
    total          = len(parsed_regex)

    print(f"  Regex parsed  : {n_regex_ok}/{total} ({n_regex_ok/total*100:.1f}%)")
    print(f"  Failed        : {n_failed_regex}/{total} ({n_failed_regex/total*100:.1f}%)")

    # Amount accuracy (where both expected and parsed are non-None)
    amount_correct = 0
    amount_total   = 0
    for p, row in zip(parsed_regex, df.itertuples()):
        expected_amt = row.expected_amount
        if pd.notna(expected_amt) and p.amount is not None:
            amount_total += 1
            if abs(p.amount - expected_amt) < 0.01:
                amount_correct += 1

    amt_acc = amount_correct / amount_total if amount_total else 0
    print(f"\n  Amount accuracy (regex-parsed): {amount_correct}/{amount_total} = {amt_acc*100:.1f}%")

    # Type accuracy
    type_correct = 0
    type_total   = 0
    for p, row in zip(parsed_regex, df.itertuples()):
        if pd.notna(row.expected_type) and p.transaction_type is not None:
            type_total += 1
            if p.transaction_type == row.expected_type:
                type_correct += 1
    type_acc = type_correct / type_total if type_total else 0
    print(f"  Type accuracy  (regex-parsed): {type_correct}/{type_total} = {type_acc*100:.1f}%")

    # Save per-message results
    rows = []
    for p, row in zip(parsed_regex, df.itertuples()):
        rows.append({
            "id":              row.id,
            "method":          p.parse_method,
            "amount_ok":       abs((p.amount or 0) - (row.expected_amount or 0)) < 0.01,
            "type_ok":         p.transaction_type == row.expected_type,
            "parsed_merchant": p.merchant,
            "expected_merchant": row.expected_merchant,
            "raw_sms":         row.raw_sms[:60],
        })
    pd.DataFrame(rows).to_csv(RESULTS / "parser_results.csv", index=False)
    print(f"\n  → Saved eval/results/parser_results.csv")

    results = {
        "total":               total,
        "regex_success":       n_regex_ok,
        "regex_success_pct":   round(n_regex_ok / total * 100, 1),
        "failed":              n_failed_regex,
        "failed_pct":          round(n_failed_regex / total * 100, 1),
        "amount_accuracy_pct": round(amt_acc * 100, 1),
        "type_accuracy_pct":   round(type_acc * 100, 1),
        "note": (
            "LLM fallback not benchmarked offline. "
            "Failed messages are intentionally unparseable (non-bank) entries in sample_sms.csv."
        ),
    }
    _save_json("parser_eval", results)
    return results


# ---------------------------------------------------------------------------
# 3. Budget engine invariant checks
# ---------------------------------------------------------------------------

def eval_budget_engine() -> dict:
    _header("3. BUDGET ENGINE INVARIANT CHECKS")

    from core.parser import parse_messages
    from core.categoriser import categorise_transactions
    from core.budget_engine import compute_budget, detect_recurring, compute_pace
    from core.nudges import rule_based_nudges

    df = pd.read_csv(SAMPLE_SMS_CSV)
    messages = df["raw_sms"].tolist()

    parsed      = parse_messages(messages, adapter=None)
    categorised = categorise_transactions(parsed, adapter=None)
    summary     = compute_budget(categorised)

    checks = {}
    failures = []

    def _check(name: str, condition: bool, detail: str = "") -> None:
        status = "PASS" if condition else "FAIL"
        icon   = "✓" if condition else "✗"
        print(f"  {icon} {name:<52} [{status}]" + (f"  {detail}" if detail else ""))
        checks[name] = {"pass": condition, "detail": detail}
        if not condition:
            failures.append(name)

    # Basic totals
    _check(
        "income >= 0",
        summary.total_income >= 0,
        f"= {summary.total_income:.2f}",
    )
    _check(
        "expense >= 0",
        summary.total_expense >= 0,
        f"= {summary.total_expense:.2f}",
    )
    _check(
        "net = income - expense",
        abs(summary.net - (summary.total_income - summary.total_expense)) < 0.01,
        f"net={summary.net:.2f} income={summary.total_income:.2f} exp={summary.total_expense:.2f}",
    )

    # Savings rate
    if summary.total_income > 0:
        expected_rate = round(
            (summary.total_income - summary.total_expense) / summary.total_income * 100, 2
        )
        _check(
            "savings_rate = net/income*100",
            abs(summary.savings_rate - expected_rate) < 0.1,
            f"{summary.savings_rate}% vs expected {expected_rate}%",
        )
    else:
        _check("savings_rate = 0 when no income", summary.savings_rate == 0)

    # 50/30/20 targets
    if summary.total_income > 0:
        _check(
            "needs_target = 50% of income",
            abs(summary.needs_target - summary.total_income * 0.50) < 0.01,
            f"{summary.needs_target:.2f}",
        )
        _check(
            "wants_target = 30% of income",
            abs(summary.wants_target - summary.total_income * 0.30) < 0.01,
            f"{summary.wants_target:.2f}",
        )
        _check(
            "savings_target = 20% of income",
            abs(summary.savings_target - summary.total_income * 0.20) < 0.01,
            f"{summary.savings_target:.2f}",
        )

    # Delta math
    _check(
        "needs_delta = needs_total - needs_target",
        abs(summary.needs_delta - (summary.needs_total - summary.needs_target)) < 0.01,
    )
    _check(
        "wants_delta = wants_total - wants_target",
        abs(summary.wants_delta - (summary.wants_total - summary.wants_target)) < 0.01,
    )

    # by_category totals are non-negative
    neg_cats = [k for k, v in summary.by_category.items() if v < 0]
    _check("all category totals >= 0", len(neg_cats) == 0,
           f"negative: {neg_cats}" if neg_cats else "")

    # by_category sum <= total_expense (some credits may be excluded)
    cat_sum = sum(summary.by_category.values())
    _check(
        "sum(by_category) <= total_expense",
        cat_sum <= summary.total_expense + 0.01,
        f"cat_sum={cat_sum:.2f} total_exp={summary.total_expense:.2f}",
    )

    # Savings chart math
    from core.savings import flat_savings_plan, stepup_savings_plan, compare_plans
    flat = flat_savings_plan(income=50000, rate=0.20, months=12)
    _check(
        "flat plan: monthly = income * rate",
        all(abs(m - 10000) < 0.01 for m in flat.monthly_amounts),
        f"first={flat.monthly_amounts[0]}",
    )
    _check(
        "flat plan: cumulative[-1] = sum(monthly)",
        abs(flat.cumulative[-1] - sum(flat.monthly_amounts)) < 0.01,
        f"cum={flat.cumulative[-1]} sum={sum(flat.monthly_amounts)}",
    )
    stepup = stepup_savings_plan(50000, 0.10, stepup_pct=0.01, raise_every_n=6, months=12)
    _check(
        "step-up: rate increases at month 7",
        stepup.monthly_amounts[6] > stepup.monthly_amounts[5],
        f"m6={stepup.monthly_amounts[5]} m7={stepup.monthly_amounts[6]}",
    )
    _check(
        "step-up saves more than flat over 12m",
        stepup.total_saved >= flat_savings_plan(50000, 0.10, 12).total_saved,
    )

    # Nudge number-check: no invented numbers
    _subheader("Nudge number-check (rule-based)")
    nudges = rule_based_nudges(summary)
    import re

    def _numbers_in_text(text: str) -> set[float]:
        return {float(n.replace(",", "")) for n in re.findall(r"[\d,]+(?:\.\d+)?", text)}

    # Collect all numbers in engine summary (including derived values)
    engine_numbers: set[float] = set()
    engine_numbers.add(summary.total_income)
    engine_numbers.add(summary.total_expense)
    engine_numbers.add(summary.net)
    engine_numbers.add(summary.savings_rate)
    engine_numbers.add(abs(summary.savings_rate))  # negative savings rate shown as abs
    engine_numbers.update(summary.by_category.values())
    engine_numbers.add(summary.needs_total)
    engine_numbers.add(summary.wants_total)
    engine_numbers.add(summary.savings_total)
    engine_numbers.add(summary.needs_target)
    engine_numbers.add(summary.wants_target)
    engine_numbers.add(summary.savings_target)
    engine_numbers.add(summary.needs_delta)
    engine_numbers.add(summary.wants_delta)
    engine_numbers.add(summary.savings_delta)
    # Derived: 10% of income (used in savings-habit nudge)
    engine_numbers.add(round(summary.total_income * 0.10))
    # Percentage labels (10, 20, 30, 50) are OK — not invented numbers
    engine_numbers.update({10.0, 20.0, 30.0, 50.0})
    # Also allow rounded versions
    engine_numbers_rounded = {round(n) for n in engine_numbers} | \
                             {round(n, 2) for n in engine_numbers} | \
                             {round(abs(n), 2) for n in engine_numbers}

    all_pass = True
    for i, nudge in enumerate(nudges, 1):
        nums_in_nudge = _numbers_in_text(nudge["text"])
        # Filter out small numbers (percentages like 10, 20 are ok; they come from engine)
        rogue = {
            n for n in nums_in_nudge
            if n > 10 and
               n not in engine_numbers_rounded and
               round(n) not in engine_numbers_rounded
        }
        passed = len(rogue) == 0
        all_pass = all_pass and passed
        print(
            f"  {'✓' if passed else '✗'} Nudge {i}: "
            f"{'no rogue numbers' if passed else f'ROGUE={rogue}'}"
        )
        print(f"    \"{nudge['text'][:80]}\"")
    _check("All nudge numbers sourced from engine", all_pass)

    # Summary
    n_pass = sum(1 for v in checks.values() if v["pass"])
    n_total = len(checks)
    print(f"\n  Result: {n_pass}/{n_total} checks passed")
    if failures:
        print(f"  Failed: {failures}")

    _save_json("budget_engine_eval", {
        "checks": checks,
        "failures": failures,
        "n_pass": n_pass,
        "n_total": n_total,
        "summary_stats": {
            "total_income":  summary.total_income,
            "total_expense": summary.total_expense,
            "net":           summary.net,
            "savings_rate":  summary.savings_rate,
            "n_transactions": summary.n_transactions,
            "n_parsed":      summary.n_parsed,
            "n_failed":      summary.n_failed,
        },
    })
    return checks


# ---------------------------------------------------------------------------
# 4. Failure case analysis
# ---------------------------------------------------------------------------

def eval_failure_cases() -> None:
    _header("4. FAILURE CASE ANALYSIS (3 real examples)")

    from scam.rules import run_rules
    from scam.classifier import ScamClassifier
    from scam.pipeline import analyse

    clf = ScamClassifier()
    clf.train(SCAM_EVAL_CSV)

    # Load test set and find genuine misclassifications
    df       = pd.read_csv(SCAM_EVAL_CSV)
    test_df  = df[df["split"] == "test"].copy()

    def _rules_verdict(text):
        r = run_rules(text)
        return "scam" if r.score >= 0.55 else "suspicious" if r.score >= 0.25 else "safe"

    test_df["pred_rules"] = test_df["text"].apply(_rules_verdict)
    test_df["pred_clf"]   = test_df["text"].apply(clf.predict)
    test_df["pred_pipeline"] = test_df["text"].apply(
        lambda t: analyse(t, classifier=clf).verdict
    )

    # Find rows where both rules AND classifier are wrong
    both_wrong = test_df[
        (test_df["pred_rules"] != test_df["label"]) &
        (test_df["pred_clf"]   != test_df["label"])
    ].head(3)

    # Fallback: at least one wrong
    if len(both_wrong) < 3:
        at_least_one_wrong = test_df[
            (test_df["pred_rules"] != test_df["label"]) |
            (test_df["pred_clf"]   != test_df["label"])
        ].head(3)
        both_wrong = at_least_one_wrong

    for i, (_, row) in enumerate(both_wrong.iterrows(), 1):
        print(f"\n  Example {i}:")
        print(f"  Text    : {row['text'][:120]}")
        print(f"  True    : {row['label']}")
        print(f"  Rules   : {row['pred_rules']}")
        print(f"  ML clf  : {row['pred_clf']}")
        print(f"  Pipeline: {row['pred_pipeline']}")

        # Explanation
        if row["label"] == "safe" and row["pred_rules"] in ("scam", "suspicious"):
            reason = (
                "FALSE POSITIVE — a legitimate bank SMS that triggered a scam keyword "
                "(e.g. 'OTP' in a genuine NPCI message, or a short URL in a delivery alert)."
            )
        elif row["label"] == "scam" and row["pred_rules"] == "safe":
            reason = (
                "FALSE NEGATIVE — a scam SMS that avoided all keyword triggers. "
                "Often job-scam or prize-scam phrased without urgency words or links."
            )
        elif row["label"] == "suspicious" and row["pred_rules"] != "suspicious":
            reason = (
                "THRESHOLD BOUNDARY — message scored near the 0.25/0.55 boundary. "
                "Small wording changes flip the verdict between safe/suspicious/scam."
            )
        else:
            reason = "MISCLASSIFICATION — see text above for context."
        print(f"  Reason  : {reason}")

    print("\n  Lessons:")
    print("  1. OTP in legitimate bank/NPCI messages causes false positives in rules engine.")
    print("  2. Sophisticated job/prize scams with no trigger keywords evade rules entirely.")
    print("  3. The 'suspicious' class is hardest — it sits between safe and scam thresholds.")
    print("  4. ML classifier helps on training-distribution text; Hinglish generalisation is weak.")
    print("  Mitigation: LLM judge handles edge cases; always show Trust Receipt for transparency.")


# ---------------------------------------------------------------------------
# 5. Save combined summary chart
# ---------------------------------------------------------------------------

def _save_summary_chart(scam_results: dict) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np

        labels  = ["Rules\nbaseline", "ML\nClassifier", "Combined\npipeline"]
        metrics = ["precision", "recall", "f1-score"]
        colours = ["#58A6FF", "#21C55D", "#FFA500"]

        fig, ax = plt.subplots(figsize=(8, 4))
        x  = np.arange(len(labels))
        bw = 0.22

        for i, (metric, colour) in enumerate(zip(metrics, colours)):
            vals = []
            for key in ["rules", "clf", "pipeline"]:
                vals.append(
                    scam_results[key]["report"].get("macro avg", {}).get(metric, 0)
                )
            ax.bar(x + (i - 1) * bw, vals, bw, label=metric.capitalize(), color=colour)

        ax.set_xticks(x)
        ax.set_xticklabels(labels, fontsize=11)
        ax.set_ylim(0, 1.05)
        ax.set_ylabel("Score (macro avg)", fontsize=11)
        ax.set_title("Artha Kavach — Scam Detection Performance", fontsize=13, pad=12)
        ax.legend()
        ax.grid(axis="y", alpha=0.3)
        fig.tight_layout()

        out = RESULTS / "scam_performance.png"
        fig.savefig(out, dpi=150)
        plt.close(fig)
        print(f"\n  → Saved eval/results/scam_performance.png")
    except Exception as exc:
        print(f"\n  Chart save skipped: {exc}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Artha Kavach evaluation suite")
    parser.add_argument(
        "--llm", action="store_true",
        help="Include LLM judge in scam eval (requires GEMINI_API_KEY)"
    )
    parser.add_argument(
        "--skip-budget", action="store_true",
        help="Skip budget engine checks (faster)"
    )
    args = parser.parse_args()

    print("\n" + "=" * 68)
    print("  ARTHA KAVACH — EVALUATION SUITE")
    print("  Results saved to: eval/results/")
    if not args.llm:
        print("  NOTE: LLM judge OFF (pass --llm to enable, costs API quota)")
    print("=" * 68)

    scam_results  = eval_scam(use_llm=args.llm)
    parser_results = eval_parser()

    if not args.skip_budget:
        eval_budget_engine()

    eval_failure_cases()
    _save_summary_chart(scam_results)

    # Final summary table
    _header("FINAL SUMMARY")
    mac_rules    = scam_results["rules"]["report"].get("macro avg", {}).get("f1-score", 0)
    mac_clf      = scam_results["clf"]["report"].get("macro avg", {}).get("f1-score", 0)
    mac_pipeline = scam_results["pipeline"]["report"].get("macro avg", {}).get("f1-score", 0)

    print(f"\n  Scam detection (macro F1 on {scam_results['n_test']}-msg test set):")
    print(f"    Rules baseline   : {mac_rules:.3f}")
    print(f"    ML Classifier    : {mac_clf:.3f}")
    print(f"    Combined pipeline: {mac_pipeline:.3f}")

    p_succ = parser_results["regex_success_pct"]
    print(f"\n  Parser (regex-only): {p_succ}% success rate on {parser_results['total']} messages")
    print(f"  Amount accuracy    : {parser_results['amount_accuracy_pct']}%")

    print(f"\n  Small-sample caveat: test set = {scam_results['n_test']} synthetic messages.")
    print("  Real-world performance may differ. Treat as directional metrics only.")
    print("\n  All detail files in eval/results/\n")


if __name__ == "__main__":
    main()
