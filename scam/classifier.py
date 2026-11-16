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

import pandas as pd

logger = logging.getLogger(__name__)

MODEL_CACHE_PATH = Path(".cache/classifier/model.pkl")


# ---------------------------------------------------------------------------
# Classifier class
# ---------------------------------------------------------------------------

class ScamClassifier:
    """TF-IDF + Logistic Regression for 3-class scam detection."""

    CLASSES = ["safe", "suspicious", "scam"]

    def __init__(self):
        self._pipeline = None   # sklearn Pipeline

    def train(self, csv_path: str | Path) -> None:
        """Train the classifier on the train split of scam_eval.csv.

        Args:
            csv_path: Path to data/scam_eval.csv
        """
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import Pipeline

        df = pd.read_csv(csv_path)
        train_df = df[df["split"] == "train"].copy()

        if train_df.empty:
            raise ValueError(f"No training rows found in {csv_path}. Check 'split' column.")

        X = train_df["text"].fillna("").tolist()
        y = train_df["label"].tolist()

        # TF-IDF with word + character n-grams (helps with Hinglish)
        tfidf = TfidfVectorizer(
            analyzer="word",
            ngram_range=(1, 2),
            min_df=1,
            max_features=5000,
            sublinear_tf=True,
            strip_accents="unicode",
        )

        lr = LogisticRegression(
            class_weight="balanced",
            max_iter=1000,
            C=1.0,
            solver="lbfgs",
            random_state=42,
        )

        self._pipeline = Pipeline([("tfidf", tfidf), ("lr", lr)])
        self._pipeline.fit(X, y)

        label_counts = pd.Series(y).value_counts().to_dict()
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

        df = pd.read_csv(csv_path)
        test_df = df[df["split"] == "test"].copy()
        if test_df.empty:
            raise ValueError("No test rows found.")

        X_test = test_df["text"].fillna("").tolist()
        y_test = test_df["label"].tolist()
        y_pred = [self.predict(x) for x in X_test]

        report = classification_report(y_test, y_pred, output_dict=True)
        cm = confusion_matrix(y_test, y_pred, labels=self.CLASSES)

        # Hinglish subset
        hinglish_df = test_df[test_df["hinglish"] == True]
        if not hinglish_df.empty:
            xh = hinglish_df["text"].fillna("").tolist()
            yh = hinglish_df["label"].tolist()
            ph = [self.predict(x) for x in xh]
            hinglish_report = classification_report(yh, ph, output_dict=True, zero_division=0)
        else:
            hinglish_report = {}

        return {
            "n_test": len(X_test),
            "classification_report": report,
            "confusion_matrix": cm.tolist(),
            "hinglish_n": len(hinglish_df),
            "hinglish_report": hinglish_report,
        }

    @property
    def is_trained(self) -> bool:
        return self._pipeline is not None


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
