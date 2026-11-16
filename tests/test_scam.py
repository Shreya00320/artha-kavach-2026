"""
tests/test_scam.py — Unit tests for Phase 3 Scam Shield.

All tests run offline (mocked LLM/retriever). No API calls.

Coverage:
  Rules engine (8 tests): OTP match, collect-request, urgency, KYC, phishing,
                          lottery, job scam, clean safe SMS scores low
  Classifier (5 tests): trains, predicts scam/safe, 3 classes, Hinglish
  LLM Judge (3 tests): fallback verdict, mock LLM call, confidence cap
  Verifier (3 tests): verified stays, unverified dropped, no KB graceful
  Pipeline (5 tests): rules-only, full mocked, classifier used, no retriever, timing
"""

import pytest
from unittest.mock import MagicMock, patch

from scam.rules import run_rules, _aggregate_score, RuleMatch
from scam.llm_judge import rules_only_verdict, run_llm_judge
from scam.verifier import verify_claims, filter_verified, _all_unverified
from scam.pipeline import analyse, ScamAnalysis
from llm.schemas import (
    ScamVerdict, RedFlag, VerifiableClaim,
    ClaimVerifyResult, ClaimVerifyItem,
)


# ---------------------------------------------------------------------------
# Rules engine tests
# ---------------------------------------------------------------------------

class TestRules:

    def test_otp_request_detected(self):
        sms = "URGENT: Share OTP 123456 to verify your SBI account."
        result = run_rules(sms)
        cats = [m.category for m in result.matches]
        assert "otp_request" in cats
        assert result.score > 0.5

    def test_collect_request_detected(self):
        sms = "Rs 1 collect request sent to verify account. Accept to get Rs 10,000 refund."
        result = run_rules(sms)
        cats = [m.category for m in result.matches]
        assert "collect_request" in cats
        assert result.score > 0.6

    def test_urgency_block_detected(self):
        sms = "Your account will be blocked in 2 hours. Act now!"
        result = run_rules(sms)
        cats = [m.category for m in result.matches]
        assert "urgency" in cats

    def test_kyc_fraud_detected(self):
        sms = "KYC update pending. Click http://bit.ly/kyc99 or account blocked."
        result = run_rules(sms)
        cats = [m.category for m in result.matches]
        assert "kyc_fraud" in cats
        assert "phishing_link" in cats
        assert result.score > 0.7

    def test_phishing_link_detected(self):
        sms = "Your HDFC refund ready. Click: http://hdfc-secure.click/refund now"
        result = run_rules(sms)
        cats = [m.category for m in result.matches]
        assert "phishing_link" in cats

    def test_lottery_scam_detected(self):
        sms = "Congratulations! You won Rs 5,00,000 in NPCI lucky draw. Pay Rs 500 processing fee to claim."
        result = run_rules(sms)
        cats = [m.category for m in result.matches]
        assert "lottery_scam" in cats
        assert result.score > 0.7

    def test_job_scam_detected(self):
        # R060: "registration fee" standalone triggers job_scam
        sms = "Part-time job offer! Pay Rs 999 registration fee to unlock your tasks and start earning."
        result = run_rules(sms)
        cats = [m.category for m in result.matches]
        assert "job_scam" in cats

    def test_clean_bank_sms_scores_low(self):
        """A real bank debit SMS should score very low or zero."""
        sms = "Rs 1,250.00 debited from A/c XX4521 on 14-Nov-26 at SWIGGY. Avl Bal: Rs 12,340.50 —SBI"
        result = run_rules(sms)
        assert result.score < 0.3
        # May have 0 matches for a clean debit SMS
        assert result.n_rules_matched <= 1

    def test_aggregate_score_noisy_or(self):
        """noisy-OR: two 0.5-weight rules → score = 1 - (0.5 * 0.5) = 0.75."""
        matches = [
            RuleMatch("R001", "A", "cat", "text", 0.5),
            RuleMatch("R002", "B", "cat", "text", 0.5),
        ]
        score = _aggregate_score(matches)
        assert abs(score - 0.75) < 0.001

    def test_no_matches_score_zero(self):
        result = run_rules("Hello, how are you?")
        assert result.score == 0.0
        assert result.n_rules_matched == 0


# ---------------------------------------------------------------------------
# Classifier tests
# ---------------------------------------------------------------------------

# Module-level fixture so classifier trains once
@pytest.fixture(scope="module")
def trained_clf():
    from scam.classifier import ScamClassifier
    c = ScamClassifier()
    c.train("data/scam_eval.csv")
    return c


class TestClassifier:
    """Train on the actual scam_eval.csv (small, fast — ~100 rows)."""

    def test_trains_without_error(self, trained_clf):
        assert trained_clf.is_trained

    def test_predicts_scam_sms(self, trained_clf):
        sms = "URGENT: Share your OTP to verify your account. Click http://bit.ly/fake now!"
        probas = trained_clf.predict_proba(sms)
        assert probas["scam"] > probas["safe"]

    def test_predicts_safe_bank_sms(self, trained_clf):
        sms = "Rs 1,250.00 debited from A/c XX4521 on 14-Nov-26 at SWIGGY. Avl Bal: Rs 12,340.50 —SBI"
        probas = trained_clf.predict_proba(sms)
        assert probas["safe"] > probas["scam"]

    def test_three_class_probabilities_sum_to_1(self, trained_clf):
        sms = "Your KYC is expiring today. Click http://bit.ly/upd8kyc to avoid account block."
        probas = trained_clf.predict_proba(sms)
        assert set(probas.keys()) == {"scam", "suspicious", "safe"}
        assert abs(sum(probas.values()) - 1.0) < 0.001

    def test_predict_returns_string_label(self, trained_clf):
        sms = "Congratulations! You won Rs 5 lakh NPCI lottery."
        label = trained_clf.predict(sms)
        assert label in {"scam", "suspicious", "safe"}


# ---------------------------------------------------------------------------
# LLM Judge tests
# ---------------------------------------------------------------------------

class TestLLMJudge:

    def _make_rule_result(self, score=0.8, n=2):
        from scam.rules import RulesResult, RuleMatch
        matches = [RuleMatch(f"R00{i}", "OTP request", "otp_request", "share otp", 0.9) for i in range(n)]
        return RulesResult(score=score, matches=matches, n_rules_matched=n, top_category="otp_request")

    def test_rules_only_verdict_scam(self):
        rule_result = self._make_rule_result(score=0.85)
        verdict = rules_only_verdict(rule_result, {"scam": 0.9, "suspicious": 0.05, "safe": 0.05})
        assert verdict.verdict == "scam"
        assert verdict.confidence <= 0.80  # capped

    def test_rules_only_verdict_safe(self):
        from scam.rules import RulesResult
        rule_result = RulesResult(score=0.0, matches=[], n_rules_matched=0, top_category="")
        verdict = rules_only_verdict(rule_result, {"scam": 0.05, "suspicious": 0.1, "safe": 0.85})
        assert verdict.verdict == "safe"

    def test_llm_judge_uses_adapter(self):
        """When adapter is available, it calls adapter.generate()."""
        rule_result = self._make_rule_result()
        mock_adapter = MagicMock()
        mock_adapter.generate.return_value = ScamVerdict(
            verdict="scam", confidence=0.95,
            red_flags=[RedFlag(flag="OTP", quote_from_message="share otp", why_it_matters="test")],
            what_to_do=["Do not share OTP"],
            claims=[],
        )
        result = run_llm_judge(
            message="Share your OTP to verify.",
            rule_result=rule_result,
            classifier_proba={"scam": 0.9, "suspicious": 0.05, "safe": 0.05},
            advisory_context="[KB001] Never share OTP.",
            adapter=mock_adapter,
        )
        assert result.verdict == "scam"
        mock_adapter.generate.assert_called_once()

    def test_llm_judge_falls_back_on_error(self):
        """When adapter raises, falls back to rules_only_verdict."""
        rule_result = self._make_rule_result(score=0.9)
        mock_adapter = MagicMock()
        mock_adapter.generate.side_effect = RuntimeError("API down")
        result = run_llm_judge(
            message="Share your OTP.",
            rule_result=rule_result,
            classifier_proba=None,
            advisory_context="",
            adapter=mock_adapter,
        )
        # Should still return a valid verdict
        assert result.verdict in {"scam", "suspicious", "safe"}


# ---------------------------------------------------------------------------
# Verifier tests
# ---------------------------------------------------------------------------

class TestVerifier:

    def _make_verdict_with_claims(self):
        return ScamVerdict(
            verdict="scam", confidence=0.9,
            red_flags=[],
            what_to_do=["Do not share OTP"],
            claims=[
                VerifiableClaim(
                    text="Banks never ask for OTP via SMS.",
                    source_id="KB001",
                ),
            ],
        )

    def test_verified_claim_kept(self):
        verdict = self._make_verdict_with_claims()
        verify_result = ClaimVerifyResult(results=[
            ClaimVerifyItem(
                claim_text="Banks never ask for OTP via SMS.",
                source_id="KB001",
                verified=True,
                evidence_quote="NPCI states OTP must never be shared...",
            )
        ])
        filtered = filter_verified(verdict, verify_result)
        assert len(filtered.claims) == 1

    def test_unverified_claim_dropped(self):
        verdict = self._make_verdict_with_claims()
        verify_result = ClaimVerifyResult(results=[
            ClaimVerifyItem(
                claim_text="Banks never ask for OTP via SMS.",
                source_id="KB001",
                verified=False,
                evidence_quote=None,
            )
        ])
        filtered = filter_verified(verdict, verify_result)
        assert len(filtered.claims) == 0

    def test_no_retriever_marks_all_unverified(self):
        verdict = self._make_verdict_with_claims()
        mock_adapter = MagicMock()
        # retriever=None → no source texts → all unverified
        result = verify_claims(verdict, retriever=None, adapter=mock_adapter)
        # With no KB available, should return all unverified without calling adapter
        assert all(not r.verified for r in result.results)
        mock_adapter.generate.assert_not_called()


# ---------------------------------------------------------------------------
# Pipeline tests
# ---------------------------------------------------------------------------

class TestPipeline:

    def _scam_msg(self):
        return "URGENT: Your KYC is expiring! Share OTP 7382 now or account blocked in 2 hours."

    def _safe_msg(self):
        return "Rs 1,250.00 debited from A/c XX4521 on 14-Nov-26 at SWIGGY. Avl Bal: Rs 12,340.50 —SBI"

    def test_rules_only_pipeline(self):
        """No adapter/retriever/classifier → rules fallback works."""
        result = analyse(self._scam_msg())
        assert result.verdict in {"scam", "suspicious"}
        assert result.llm_used is False
        assert result.retriever_used is False
        assert result.trust_receipt is not None

    def test_safe_msg_rules_only(self):
        result = analyse(self._safe_msg())
        assert result.verdict in {"safe", "suspicious"}
        assert result.rule_result.score < 0.4

    def test_pipeline_with_mock_adapter(self):
        mock_adapter = MagicMock()
        mock_adapter.generate.return_value = ScamVerdict(
            verdict="scam", confidence=0.95,
            red_flags=[RedFlag(flag="OTP", quote_from_message="Share OTP", why_it_matters="test")],
            what_to_do=["Do not share OTP"],
            claims=[],
        )
        result = analyse(self._scam_msg(), adapter=mock_adapter)
        assert result.verdict == "scam"
        assert result.llm_used is True
        assert result.elapsed_ms >= 0

    def test_pipeline_with_mock_classifier(self):
        mock_clf = MagicMock()
        mock_clf.predict_proba.return_value = {"scam": 0.92, "suspicious": 0.05, "safe": 0.03}
        result = analyse(self._scam_msg(), classifier=mock_clf)
        assert result.classifier_used is True
        assert result.classifier_proba is not None
        assert result.classifier_proba["scam"] == pytest.approx(0.92)

    def test_trust_receipt_has_detector_votes(self):
        mock_clf = MagicMock()
        mock_clf.predict_proba.return_value = {"scam": 0.9, "suspicious": 0.07, "safe": 0.03}
        result = analyse(self._scam_msg(), classifier=mock_clf)
        tr = result.trust_receipt
        assert tr is not None
        # At least rules + classifier + LLM-or-fallback
        assert len(tr.detector_votes) >= 2
        # All vote labels are valid
        for vote in tr.detector_votes:
            assert vote.verdict in {"scam", "suspicious", "safe"}
