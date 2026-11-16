"""
scam/pipeline.py — Scam Shield orchestration pipeline.

Runs all 4 steps in sequence:
  1. Rules baseline  → RulesResult
  2. ML Classifier   → dict of probabilities
  3. RAG retrieval   → advisory context string + source docs
  4. LLM judge       → ScamVerdict
  5. Claim verifier  → ClaimVerifyResult
  6. Trust Receipt   → TrustReceipt

Graceful degradation:
  - If classifier is None → skip step 2 (classifier_proba = None)
  - If retriever is None  → skip RAG (advisory_context = "")
  - If adapter is None    → skip LLM (use rules_only_verdict)
  - If verifier LLM fails → mark all claims unverified

Public API:
  ScamAnalysis  — full result dataclass
  analyse(message, adapter, retriever, classifier) -> ScamAnalysis
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from scam.rules import RulesResult, run_rules
from llm.schemas import ScamVerdict, ClaimVerifyResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class ScamAnalysis:
    """Complete output of the Scam Shield pipeline."""
    # Input
    message: str

    # Step 1: Rules
    rule_result: RulesResult

    # Step 2: Classifier
    classifier_proba: Optional[dict]   # {"scam": float, "suspicious": float, "safe": float}

    # Step 3: RAG
    sources: list = field(default_factory=list)   # list[RetrievalResult]
    advisory_context: str = ""

    # Step 4: LLM Judge
    verdict: str = "suspicious"
    confidence: float = 0.0
    red_flags: list = field(default_factory=list)
    what_to_do: list[str] = field(default_factory=list)

    # Step 5: Claim verification
    verify_result: Optional[ClaimVerifyResult] = None
    verified_claims_only: list = field(default_factory=list)

    # Step 6: Trust Receipt
    trust_receipt: Optional[object] = None   # TrustReceipt

    # Metadata
    elapsed_ms: float = 0.0
    llm_used: bool = False
    retriever_used: bool = False
    classifier_used: bool = False


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def analyse(
    message: str,
    adapter=None,
    retriever=None,
    classifier=None,
    top_k_passages: int = 3,
) -> ScamAnalysis:
    """Run the full Scam Shield pipeline on a message.

    Args:
        message: Raw SMS / WhatsApp text to analyse.
        adapter: LLM adapter. If None, uses rules + classifier only.
        retriever: RAG Retriever. If None, no KB passages are retrieved.
        classifier: ScamClassifier. If None, classifier step is skipped.
        top_k_passages: Number of KB passages to retrieve.

    Returns:
        ScamAnalysis with all outputs populated.
    """
    t0 = time.monotonic()

    # ----- Step 1: Rules -----
    rule_result = run_rules(message)
    logger.info("[Rules] score=%.3f, n_matched=%d", rule_result.score, rule_result.n_rules_matched)

    # ----- Step 2: Classifier -----
    classifier_proba = None
    classifier_used = False
    if classifier is not None:
        try:
            classifier_proba = classifier.predict_proba(message)
            classifier_used = True
            logger.info("[Classifier] %s", classifier_proba)
        except Exception as exc:
            logger.warning("[Classifier] failed: %s", exc)

    # ----- Step 3: RAG retrieval -----
    sources = []
    advisory_context = ""
    retriever_used = False
    if retriever is not None:
        try:
            sources = retriever.retrieve(message, top_k=top_k_passages)
            advisory_context = retriever.retrieve_as_context(message, top_k=top_k_passages)
            retriever_used = True
            logger.info("[RAG] retrieved %d passages", len(sources))
        except Exception as exc:
            logger.warning("[RAG] failed: %s", exc)

    # ----- Step 4: LLM Judge (or fallback) -----
    llm_used = False
    if adapter is not None:
        from scam.llm_judge import run_llm_judge
        verdict_obj = run_llm_judge(message, rule_result, classifier_proba, advisory_context, adapter)
        llm_used = True
    else:
        from scam.llm_judge import rules_only_verdict
        verdict_obj = rules_only_verdict(rule_result, classifier_proba)

    # ----- Step 5: Claim verification -----
    verify_result = None
    if verdict_obj.claims and adapter is not None and retriever is not None:
        from scam.verifier import verify_claims, filter_verified
        verify_result = verify_claims(verdict_obj, retriever, adapter)
        verdict_obj = filter_verified(verdict_obj, verify_result)

    # ----- Step 6: Trust Receipt -----
    analysis = ScamAnalysis(
        message=message,
        rule_result=rule_result,
        classifier_proba=classifier_proba,
        sources=sources,
        advisory_context=advisory_context,
        verdict=verdict_obj.verdict,
        confidence=verdict_obj.confidence,
        red_flags=verdict_obj.red_flags,
        what_to_do=verdict_obj.what_to_do,
        verify_result=verify_result,
        verified_claims_only=verdict_obj.claims,
        llm_used=llm_used,
        retriever_used=retriever_used,
        classifier_used=classifier_used,
        elapsed_ms=round((time.monotonic() - t0) * 1000, 1),
    )

    from core.trust_receipt import build_scam_receipt
    analysis.trust_receipt = build_scam_receipt(analysis)

    logger.info(
        "[Pipeline] verdict=%s conf=%.2f elapsed=%.0fms",
        analysis.verdict, analysis.confidence, analysis.elapsed_ms,
    )
    return analysis
