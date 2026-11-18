"""
scam/train_deep.py — train the deep scam model and compare it with the TF-IDF baselines.

    python -m scam.train_deep            # train, evaluate, save models/scam_dl.npz
    python -m scam.train_deep --no-save  # evaluate only

Training data : data/scam_eval.csv (train split) + data/scam_train_extra.csv (generated)
Test data     : data/scam_eval.csv (test split)        the original test set
                data/ordinary_text_eval.csv            hand-written ordinary texts (must be "safe")
                data/scam_heldout.csv                  hand-written scam / suspicious texts
None of the test files is used for training.
"""

from __future__ import annotations

import csv
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scam.classifier import ScamClassifier, load_split  # noqa: E402
from scam.deep_model import DEFAULT_MODEL_PATH, DeepScamClassifier  # noqa: E402

D = ROOT / "data"


def _rows(name: str, split: str | None = None) -> list[dict]:
    return load_split(D / name, split)


def _metrics(predict, rows: list[dict]) -> dict:
    n = len(rows)
    preds = [predict(r["text"]) for r in rows]
    correct = sum(p == r["label"] for p, r in zip(preds, rows))
    flagged = sum(p != "safe" for p in preds)
    scam_rows = [(p, r) for p, r in zip(preds, rows) if r["label"] == "scam"]
    return {
        "n": n, "accuracy": correct / n, "flagged_pct": flagged / n,
        "scam_recall": (sum(p == "scam" for p, _ in scam_rows) / len(scam_rows)) if scam_rows else None,
        "wrong": [(r["text"], r["label"], p) for p, r in zip(preds, rows) if p != r["label"]],
    }


def evaluate(name: str, predict) -> None:
    orig = _metrics(predict, _rows("scam_eval.csv", "test"))
    ordinary = _metrics(predict, _rows("ordinary_text_eval.csv"))
    held = _metrics(predict, _rows("scam_heldout.csv"))
    ext_test = D / "external" / "sms_ham_test.csv"
    print(f"\n{name}")
    if ext_test.exists():
        sms = _metrics(predict, load_split(ext_test, "test"))
        print(f"  real SMS chat (n={sms['n']})        FALSE ALARMS {sms['flagged_pct']:.0%}  (UCI ham messages, never trained on)")
    print(f"  original test (n={orig['n']})        accuracy {orig['accuracy']:.0%}   scam recall {orig['scam_recall']:.0%}")
    print(f"  ordinary text (n={ordinary['n']})     FALSE ALARMS {ordinary['flagged_pct']:.0%}  (flagged as suspicious/scam; lower is better)")
    print(f"  new scams     (n={held['n']})        accuracy {held['accuracy']:.0%}   caught (not 'safe') {held['flagged_pct']:.0%}   scam recall {held['scam_recall']:.0%}")
    return ordinary, held


def main() -> int:
    train = _rows("scam_eval.csv", "train") + _rows("scam_train_extra.csv", "train")
    ext = D / "external" / "sms_ham_train.csv"
    if ext.exists():
        train += load_split(ext, "train")
    else:
        print("note: data/external/sms_ham_train.csv missing — run data/fetch_sms_ham.py for real ordinary text")
    # Optional, OFF by default: extra ordinary text from a third-party dataset of unknown licence
    # (see data/fetch_vinit_ham.py). A/B tests showed no measurable gain over the shipped model,
    # so it is not used unless you ask:  python -m scam.train_deep --vinit-n=1200
    vin = D / "external" / "vinit_ham_train.csv"
    n_extra = next((int(a.split("=")[1]) for a in sys.argv if a.startswith("--vinit-n=")), 0)
    if vin.exists() and n_extra > 0:
        train += load_split(vin, "train")[:n_extra]
    print(f"training rows: {len(train)}")

    # --- baselines -------------------------------------------------------
    base = ScamClassifier()
    base.train(D / "scam_eval.csv")
    evaluate("BASELINE  TF-IDF + logistic regression (original 108 training rows)", base.predict)

    combined = Path(tempfile.mkdtemp()) / "combined.csv"
    with open(combined, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id", "label", "text", "language", "hinglish", "split", "notes"])
        w.writeheader()
        for r in train:
            w.writerow({"id": r.get("id", ""), "label": r["label"], "text": r["text"], "language": r.get("language", ""),
                        "hinglish": r.get("hinglish", ""), "split": "train", "notes": ""})
    lr2 = ScamClassifier()
    lr2.train(combined)
    evaluate("BASELINE+ TF-IDF + logistic regression (same new training data)", lr2.predict)

    # --- deep model ------------------------------------------------------
    print("\ntraining deep model (PyTorch)…")
    deep = DeepScamClassifier()
    deep.train(train)
    ordinary, held = evaluate("DEEP      hashed n-gram embeddings + 2 hidden layers (ensemble of 3)", deep.predict)

    if "--verbose" in sys.argv:
        for title, m in (("ordinary text mistakes", ordinary), ("new scam mistakes", held)):
            print(f"\n{title}:")
            for text, want, got in m["wrong"]:
                print(f"  want {want:<10} got {got:<10} | {text[:90]}")

    if "--no-save" not in sys.argv:
        deep.save(DEFAULT_MODEL_PATH)
        print(f"\nsaved {DEFAULT_MODEL_PATH.relative_to(ROOT)} ({DEFAULT_MODEL_PATH.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
