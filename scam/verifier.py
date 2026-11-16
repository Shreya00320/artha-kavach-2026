"""
scam/verifier.py — Claim verification (second LLM call).

For each claim in the ScamVerdict, checks whether the cited KB passage
actually supports the claim. Marks each as "verified" or "unsupported".
Drops unsupported claims from the final Trust Receipt.

Falls back gracefully (marks all claims as unverified) if LLM fails.

Public API:
  verify_claims(verdict, retriever, adapter) -> ClaimVerifyResult
  filter_verified(verdict, verify_result) -> ScamVerdict  # drops unverified claims
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from llm.schemas import ScamVerdict, ClaimVerifyResult, ClaimVerifyItem, VerifiableClaim

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def verify_claims(
    verdict: ScamVerdict,
    retriever,                   # rag.retrieve.Retriever or None
    adapter,
) -> ClaimVerifyResult:
    """Verify each claim in the verdict against its cited KB passage.

    Args:
        verdict: ScamVerdict from run_llm_judge().
        retriever: Retriever with the loaded FAISS index (can be None).
        adapter: LLM adapter for the second verification call.

    Returns:
        ClaimVerifyResult with verified/unverified status for each claim.
    """
    if not verdict.claims:
        return ClaimVerifyResult(results=[])

    # Build a map: source_id -> document text (from the FAISS index)
    source_texts: dict[str, str] = {}
    if retriever is not None:
        for doc in retriever._index.documents:
            source_texts[doc.id] = doc.text

    # Build the claims-and-passages block for the prompt
    claims_block = _build_claims_block(verdict.claims, source_texts)

    if not claims_block.strip():
        # No KB passages available — mark all unverified
        return _all_unverified(verdict.claims, reason="KB not available")

    from llm.prompts import CLAIM_VERIFY_PROMPT_V1

    prompt = CLAIM_VERIFY_PROMPT_V1.format(claims_and_passages=claims_block)

    try:
        result: ClaimVerifyResult = adapter.generate(
            prompt=prompt,
            response_schema=ClaimVerifyResult,
            temperature=0.0,
        )
        logger.info(
            "Claim verification: %d/%d verified",
            sum(1 for r in result.results if r.verified),
            len(result.results),
        )
        return result
    except Exception as exc:
        logger.warning("Claim verification LLM failed (%s) — marking all unverified.", exc)
        return _all_unverified(verdict.claims, reason=str(exc))


def filter_verified(verdict: ScamVerdict, verify_result: ClaimVerifyResult) -> ScamVerdict:
    """Return a new ScamVerdict with only verified claims kept.

    Unverified claims are dropped entirely (not just flagged) to prevent
    ungrounded statements appearing in the Trust Receipt.
    """
    if not verify_result.results:
        # No verification done — drop all claims to be safe
        return ScamVerdict(
            verdict=verdict.verdict,
            confidence=verdict.confidence,
            red_flags=verdict.red_flags,
            what_to_do=verdict.what_to_do,
            claims=[],
        )

    verified_ids = {
        (r.claim_text, r.source_id)
        for r in verify_result.results
        if r.verified
    }

    kept_claims = [
        c for c in verdict.claims
        if (c.text, c.source_id) in verified_ids
    ]

    return ScamVerdict(
        verdict=verdict.verdict,
        confidence=verdict.confidence,
        red_flags=verdict.red_flags,
        what_to_do=verdict.what_to_do,
        claims=kept_claims,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_claims_block(claims: list[VerifiableClaim], source_texts: dict[str, str]) -> str:
    """Format claims and their cited passages for the verification prompt."""
    lines = []
    for i, claim in enumerate(claims, 1):
        passage = source_texts.get(claim.source_id, "")
        if not passage:
            # Can't verify without the passage — will be marked unverified
            continue
        lines.append(f"Claim {i}:")
        lines.append(f"  text: {claim.text}")
        lines.append(f"  source_id: {claim.source_id}")
        lines.append(f"  passage: {passage[:600]}")  # limit passage length
        lines.append("")
    return "\n".join(lines)


def _all_unverified(claims: list[VerifiableClaim], reason: str = "") -> ClaimVerifyResult:
    return ClaimVerifyResult(results=[
        ClaimVerifyItem(
            claim_text=c.text,
            source_id=c.source_id,
            verified=False,
            evidence_quote=f"Verification unavailable: {reason}",
        )
        for c in claims
    ])
