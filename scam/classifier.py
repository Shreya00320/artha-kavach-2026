"""
scam/classifier.py — TF-IDF + Logistic Regression scam classifier.

Trained on data/scam_eval.csv (train split, seed=42).
3-class: scam / suspicious / safe
Returns per-class probabilities.

Saves trained model to .cache/classifier/model.pkl (auto-trains on first use).

Public API:
  ScamClassifier — class with train(), predict_proba(), predict()
  get_classifier(csv_path, cache_dir) -> ScamClassifier  # loads or trains
"""

from __future__ import annotations

import logging
import pickle
from pathlib import Path
from typing import Optional

import csv
from collections import Counter

logger = logging.getLogger(__name__)

MODEL_CACHE_PATH = Path(".cache/classifier/model.pkl")


# ---------------------------------------------------------------------------
# Classifier class
# ---------------------------------------------------------------------------

class ScamClassifier:
    """TF-IDF + Logistic Regression for 3-class scam detection."""

    CLASSES = ["safe", "suspicious", "scam"]

    def __init__(self, features: str = "word+char"):
        """
        Args:
            features: "word" (word 1-2 grams) or "word+char" (word 1-2 grams plus
                character 2-5 grams, which copes better with Hinglish spelling
                variants such as "bhejo"/"bhejein").
        """
        if features not in ("word", "word+char"):
            raise ValueError(f"Unknown features {features!r}")
        self.features = features
        self._pipeline = None   # sklearn Pipeline

    def train(self, csv_path: str | Path) -> None:
        """Train the classifier on the train split of scam_eval.csv.

        Args:
            csv_path: Path to data/scam_eval.csv
        """
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import FeatureUnion, Pipeline

        train_rows = load_split(csv_path, "train")
        if not train_rows:
            raise ValueError(f"No training rows found in {csv_path}. Check 'split' column.")

        X = [r["text"] for r in train_rows]
        y = [r["label"] for r in train_rows]

        word_tfidf = TfidfVectorizer(
            analyzer="word",
            ngram_range=(1, 2),
            min_df=1,
            max_features=5000,
            sublinear_tf=True,
            strip_accents="unicode",
        )
        if self.features == "word+char":
            # Character n-grams inside word boundaries help with Hinglish spellings
            char_tfidf = TfidfVectorizer(
                analyzer="char_wb",
                ngram_range=(2, 5),
                min_df=1,
                max_features=20000,
                sublinear_tf=True,
                strip_accents="unicode",
            )
            tfidf = FeatureUnion([("word", word_tfidf), ("char", char_tfidf)])
        else:
            tfidf = word_tfidf

        lr = LogisticRegression(
            class_weight="balanced",
            max_iter=1000,
            C=1.0,
            solver="lbfgs",
            random_state=42,
        )

        self._pipeline = Pipeline([("tfidf", tfidf), ("lr", lr)])
        self._pipeline.fit(X, y)

        label_counts = dict(Counter(y))
        logger.info("Classifier trained on %d samples: %s", len(X), label_counts)

    def save(self, path: str | Path = MODEL_CACHE_PATH) -> None:
        """Save the trained pipeline to disk."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(self._pipeline, f)
        logger.info("Classifier saved to %s", path)

    def load(self, path: str | Path = MODEL_CACHE_PATH) -> None:
        """Load a trained pipeline from disk."""
        path = Path(path)
        with open(path, "rb") as f:
            self._pipeline = pickle.load(f)
        logger.info("Classifier loaded from %s", path)

    def predict_proba(self, text: str) -> dict[str, float]:
        """Return per-class probabilities.

        Returns:
            dict with keys "safe", "suspicious", "scam" and float values summing to 1.
        """
        if self._pipeline is None:
            raise RuntimeError("Classifier not trained or loaded. Call train() or load() first.")
        proba = self._pipeline.predict_proba([text])[0]
        classes = self._pipeline.classes_
        return {cls: round(float(p), 4) for cls, p in zip(classes, proba)}

    def predict(self, text: str) -> str:
        """Return the most probable class label."""
        probas = self.predict_proba(text)
        return max(probas, key=probas.get)

    def evaluate(self, csv_path: str | Path) -> dict:
        """Evaluate on the test split and return a metrics dict."""
        from sklearn.metrics import classification_report, confusion_matrix

        test_rows = load_split(csv_path, "test")
        if not test_rows:
            raise ValueError("No test rows found.")

        X_test = [r["text"] for r in test_rows]
        y_test = [r["label"] for r in test_rows]
        y_pred = [self.predict(x) for x in X_test]

        report = classification_report(y_test, y_pred, output_dict=True)
        cm = confusion_matrix(y_test, y_pred, labels=self.CLASSES)

        # Hinglish subset
        hinglish_rows = [r for r in test_rows if r["hinglish"]]
        if hinglish_rows:
            xh = [r["text"] for r in hinglish_rows]
            yh = [r["label"] for r in hinglish_rows]
            ph = [self.predict(x) for x in xh]
            hinglish_report = classification_report(yh, ph, output_dict=True, zero_division=0)
        else:
            hinglish_report = {}

        return {
            "n_test": len(X_test),
            "classification_report": report,
            "confusion_matrix": cm.tolist(),
            "hinglish_n": len(hinglish_rows),
            "hinglish_report": hinglish_report,
        }

    @property
    def is_trained(self) -> bool:
        return self._pipeline is not None


# ---------------------------------------------------------------------------
# Data loading (stdlib only — no pandas needed to train or run the classifier)
# ---------------------------------------------------------------------------

def load_split(csv_path: str | Path, split: Optional[str] = None) -> list[dict]:
    """Read scam_eval.csv rows as dicts, optionally filtered by the 'split' column.

    Each row has: id, label, text, hinglish (bool), split, plus any other columns.
    """
    rows = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if split is not None and row.get("split") != split:
                continue
            row["text"] = (row.get("text") or "").strip()
            row["hinglish"] = str(row.get("hinglish", "")).strip().lower() == "true"
            rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# Factory function
# ---------------------------------------------------------------------------

def get_classifier(
    csv_path: str | Path,
    cache_path: str | Path = MODEL_CACHE_PATH,
    force_retrain: bool = False,
) -> ScamClassifier:
    """Load from cache or train a new classifier.

    Args:
        csv_path: Path to data/scam_eval.csv
        cache_path: Where to save/load the pickled model
        force_retrain: If True, retrain even if cache exists

    Returns:
        Trained ScamClassifier ready to use.
    """
    clf = ScamClassifier()
    cache_path = Path(cache_path)

    if not force_retrain and cache_path.exists():
        try:
            clf.load(cache_path)
            return clf
        except Exception as exc:
            logger.warning("Failed to load cached classifier (%s) — retraining.", exc)

    clf.train(csv_path)
    clf.save(cache_path)
    return clf
