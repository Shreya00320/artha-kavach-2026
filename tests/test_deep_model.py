"""Tests for the deep scam model and its end-to-end behaviour on ordinary text.

Inference is numpy-only, so these run without torch. Training (needs torch) is not re-run here;
the shipped weights in models/scam_dl.npz are what the app uses.
"""

import ast
from pathlib import Path

import pytest

from scam.classifier import load_split
from scam.deep_model import DEFAULT_MODEL_PATH, DeepScamClassifier, featurize, load_default
from scam.pipeline import analyse

ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(not DEFAULT_MODEL_PATH.exists(), reason="models/scam_dl.npz not built")


@pytest.fixture(scope="module")
def clf() -> DeepScamClassifier:
    c = load_default()
    assert c is not None and c.is_trained
    return c


def test_featurize_is_deterministic_and_normalises():
    a = featurize("Pay Rs 1,500 now at http://bit.ly/abc or call 9876543210")
    assert a == featurize("Pay Rs 1,500 now at http://bit.ly/abc or call 9876543210")
    # different phone numbers / amounts map to the same placeholders
    assert featurize("call 9876543210 now") == featurize("call 9123456789 now")
    assert featurize("") and featurize("   ")        # never empty


def test_probabilities_are_valid(clf):
    p = clf.predict_proba("hello there")
    assert set(p) == {"safe", "suspicious", "scam"}
    assert abs(sum(p.values()) - 1.0) < 0.01


def test_inference_module_does_not_import_torch_at_top_level():
    """The deployed app must not need torch: only train() may import it."""
    tree = ast.parse((ROOT / "scam" / "deep_model.py").read_text(encoding="utf-8"))
    top_level = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    names = {a.name.split(".")[0] for n in top_level for a in n.names}
    names |= {n.module.split(".")[0] for n in top_level if isinstance(n, ast.ImportFrom) and n.module}
    assert "torch" not in names


@pytest.mark.parametrize("text", [
    "hey are we still meeting for lunch tomorrow?",
    "Can you send me the notes from yesterday's class",
    "Meeting moved to 4 pm, see you in the conference room",
    "I'm running late, traffic is terrible",
    "Mom: bring milk on your way home",
    "Happy birthday! Have a great day",
    "Your OTP for login is 456123. Do not share it with anyone.",
    "Rs 250.00 debited from A/c XX1 at SWIGGY. Avl Bal Rs 1000 -SBI",
])
def test_ordinary_text_is_safe_end_to_end(clf, text):
    """The reported bug: normal messages were labelled scam/suspicious."""
    assert analyse(text, classifier=clf).verdict == "safe"


@pytest.mark.parametrize("text", [
    "Your KYC is expired, click http://bit.ly/kyc-update immediately or your account will be frozen",
    "Congratulations! You won Rs 25 lakh in KBC lottery. Pay Rs 5000 processing fee to claim.",
    "Share the OTP you received to avoid account suspension",
    "I am from CBI. You are under digital arrest. Stay on the video call and transfer money.",
])
def test_scams_are_still_flagged(clf, text):
    assert analyse(text, classifier=clf).verdict in ("scam", "suspicious")


def test_heldout_quality_gates(clf):
    """Hand-written held-out sets (never trained on). Gates sit a little below measured results."""
    ordinary = load_split(ROOT / "data" / "ordinary_text_eval.csv")
    flagged = [r for r in ordinary if analyse(r["text"], classifier=clf).verdict != "safe"]
    called_scam = [r for r in ordinary if analyse(r["text"], classifier=clf).verdict == "scam"]
    assert len(flagged) / len(ordinary) <= 0.05
    assert not called_scam

    scams = load_split(ROOT / "data" / "scam_heldout.csv")
    caught = [r for r in scams if analyse(r["text"], classifier=clf).verdict != "safe"]
    assert len(caught) / len(scams) >= 0.92

    ext = ROOT / "data" / "external" / "sms_ham_test.csv"
    if ext.exists():                       # optional third-party data (git-ignored)
        sms = load_split(ext, "test")
        bad = [r for r in sms if analyse(r["text"], classifier=clf).verdict != "safe"]
        assert len(bad) / len(sms) <= 0.03


@pytest.mark.parametrize("text", [
    "Your OTP for login is 456123. Do not share this OTP.",
    "Never share your OTP with anyone, including bank staff. -SBI",
    "Don't share your PIN or password with anyone.",
])
def test_otp_warnings_do_not_trigger_share_otp_rule(text):
    """Genuine bank OTP messages *warn* against sharing; the rule must not read that as a request."""
    from scam.rules import run_rules
    assert run_rules(text).score == 0.0


@pytest.mark.parametrize("text", [
    "Share your OTP to receive a refund",
    "please do not hesitate to share your OTP with our agent",
    "Send your PIN to confirm",
])
def test_otp_requests_still_trigger(text):
    from scam.rules import run_rules
    assert run_rules(text).score >= 0.5
