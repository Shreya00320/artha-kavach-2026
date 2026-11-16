"""
core/trust_receipt.py — Trust Receipt component (reusable by all modules).

Attaches to any AI output:
  - Sources used (KB doc id, title, publisher, URL)
  - Claims checked + verification status
  - Code-computed values (formula + inputs — for budget numbers)
  - Confidence note
  - Which detectors agreed (for Scam Shield)

This is a data model only. Rendering happens in the UI (Phase 4).

Public API:
  TrustReceipt — dataclass
  build_scam_receipt(scam_analysis) -> TrustReceipt
  build_budget_receipt(summary, nudges) -> TrustReceipt
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SourceCitation:
    """A single cited source document."""
    source_id: str
    title: str
    publisher: str
    url: str
    snippet: str = ""       # short excerpt used


@dataclass
class VerifiedClaim:
    """A claim with its verification status."""
    claim_text: str
    source_id: str
    verified: bool
    evidence_quote: Optional[str] = None


@dataclass
class CodeComputedValue:
    """A number computed by code, with its formula shown for transparency."""
    label: str              # e.g. "Monthly food spend"
    value: float
    unit: str               # e.g. "INR", "%"
    formula: str            # e.g. "sum(debits where category='Food')"
    inputs: str             # e.g. "7 transactions"


@dataclass
class DetectorVote:
    """One detector's vote in the Scam Shield pipeline."""
    detector: str           # "Rules", "Classifier", "LLM Judge"
    verdict: str            # "scam" | "suspicious" | "safe" | "N/A"
    score: float            # 0–1 confidence/probability


@dataclass
class TrustReceipt:
    """Complete Trust Receipt — attached to any AI output for transparency."""
    # Sources
    sources: list[SourceCitation] = field(default_factory=list)

    # Claims (Scam Shield)
    verified_claims: list[VerifiedClaim] = field(default_factory=list)
    n_claims_verified: int = 0
    n_claims_total: int = 0

    # Code-computed values (Smart Budget)
    code_computed: list[CodeComputedValue] = field(default_factory=list)

    # Detector votes (Scam Shield)
    detector_votes: list[DetectorVote] = field(default_factory=list)
    detectors_agreed: Optional[bool] = None

    # Confidence note
    confidence_note: str = ""

    # Disclaimer
    disclaimer: str = (
        "Artha Kavach is an educational tool. It does not give financial or legal advice. "
        "Always verify with your bank or the official cybercrime.gov.in portal."
    )


# ---------------------------------------------------------------------------
# Factory: Scam Shield receipt
# ---------------------------------------------------------------------------

def build_scam_receipt(scam_analysis: "ScamAnalysis") -> TrustReceipt:  # type: ignore[name-defined]
    """Build a TrustReceipt from a completed ScamAnalysis."""
    # Sources from retrieval results
    sources = [
        SourceCitation(
            source_id=r.source_id,
            title=r.title,
            publisher=r.publisher,
            url=r.url,
            snippet=r.snippet,
        )
        for r in (scam_analysis.sources or [])
    ]

    # Verified claims
    verified_claims = [
        VerifiedClaim(
            claim_text=c.claim_text,
            source_id=c.source_id,
            verified=c.verified,
            evidence_quote=c.evidence_quote,
        )
        for c in (scam_analysis.verify_result.results if scam_analysis.verify_result else [])
    ]
    n_verified = sum(1 for c in verified_claims if c.verified)

    # Detector votes
    votes = []
    if scam_analysis.rule_result is not None:
        rule_verdict = (
            "scam" if scam_analysis.rule_result.score >= 0.55
            else "suspicious" if scam_analysis.rule_result.score >= 0.25
            else "safe"
        )
        votes.append(DetectorVote("Rules engine", rule_verdict, scam_analysis.rule_result.score))

    if scam_analysis.classifier_proba is not None:
        clf_scam = scam_analysis.classifier_proba.get("scam", 0)
        clf_verdict = (
            "scam" if clf_scam >= 0.55
            else "suspicious" if clf_scam >= 0.30
            else "safe"
        )
        votes.append(DetectorVote("ML Classifier", clf_verdict, clf_scam))

    votes.append(DetectorVote(
        "LLM Judge", scam_analysis.verdict, scam_analysis.confidence
    ))

    # Agreement check
    final_verdicts = {v.verdict for v in votes}
    agreed = len(final_verdicts) == 1

    # Confidence note
    conf = scam_analysis.confidence
    if conf >= 0.85:
        conf_note = "High confidence — multiple detectors agree."
    elif conf >= 0.60:
        conf_note = "Moderate confidence. Treat with caution."
    else:
        conf_note = "Low confidence — not enough evidence to be certain. Treat with caution."

    return TrustReceipt(
        sources=sources,
        verified_claims=verified_claims,
        n_claims_verified=n_verified,
        n_claims_total=len(verified_claims),
        detector_votes=votes,
        detectors_agreed=agreed,
        confidence_note=conf_note,
    )


# ---------------------------------------------------------------------------
# Factory: Smart Budget receipt
# ---------------------------------------------------------------------------

def build_budget_receipt(summary: "BudgetSummary") -> TrustReceipt:  # type: ignore[name-defined]
    """Build a TrustReceipt for the Smart Budget module."""
    code_computed = [
        CodeComputedValue(
            label="Total income",
            value=summary.total_income,
            unit="INR",
            formula="sum(amount where transaction_type='credit' and category='Salary')",
            inputs=f"{summary.n_parsed} transactions parsed",
        ),
        CodeComputedValue(
            label="Total expenses",
            value=summary.total_expense,
            unit="INR",
            formula="sum(amount where transaction_type='debit')",
            inputs=f"{summary.n_parsed} transactions parsed",
        ),
        CodeComputedValue(
            label="Savings rate",
            value=summary.savings_rate,
            unit="%",
            formula="(income − expense) / income × 100",
            inputs=f"income={summary.total_income}, expense={summary.total_expense}",
        ),
        CodeComputedValue(
            label="Needs (50% bucket)",
            value=summary.needs_total,
            unit="INR",
            formula="sum(Food + Rent + EMI_Loan + Utilities + Healthcare + Education)",
            inputs=", ".join(
                f"{k}={v:.0f}" for k, v in summary.by_category.items()
                if k in {"Food", "Rent", "EMI_Loan", "Utilities", "Healthcare", "Education"}
            ) or "none",
        ),
    ]

    # KB sources for budget advice
    sources = [
        SourceCitation(
            source_id="KB011",
            title="50/30/20 Budgeting Rule",
            publisher="RBI Financial Literacy Portal",
            url="https://rbi.org.in/financialeducation",
            snippet="Divide take-home income: 50% Needs, 30% Wants, 20% Savings.",
        ),
        SourceCitation(
            source_id="KB012",
            title="Save More Tomorrow (SMarT)",
            publisher="Thaler & Benartzi (2004)",
            url="https://www.jstor.org/stable/10.1086/426038",
            snippet="Pre-commit to increasing savings rate at each income raise.",
        ),
    ]

    return TrustReceipt(
        sources=sources,
        code_computed=code_computed,
        confidence_note=(
            f"All numbers computed by code from {summary.n_parsed} parsed transactions. "
            f"{summary.n_failed} messages could not be parsed."
        ),
    )
