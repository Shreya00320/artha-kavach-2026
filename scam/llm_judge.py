"""
scam/llm_judge.py — LLM-based scam verdict judge.

Receives: message text, rule hits, classifier probability, advisory context.
Returns: ScamVerdict (verdict, confidence, red_flags, what_to_do, claims).

Falls back to rules-based verdict if LLM call fails (so the demo never breaks).

Public API:
  run_llm_judge(message, rule_result, classifier_proba, advisory_context, adapter) -> ScamVerdict
  rules_only_verdict(rule_result, classifier_proba) -> ScamVerdict
"""

from __future__ import annotations

import logging
from typing import Optional

from llm.schemas import ScamVerdict, RedFlag, VerifiableClaim
from scam.rules import RulesResult

logger = logging.getLogger(__name__)

_SEVERITY = {"safe": 0, "suspicious": 1, "scam": 2}


# ---------------------------------------------------------------------------
# Fallback: rules-only verdict (no LLM)
# ---------------------------------------------------------------------------

def rules_only_verdict(
    rule_result: RulesResult,
    classifier_proba: Optional[dict] = None,
) -> ScamVerdict:
    """Produce a verdict from rules + classifier only (no LLM).

    Used as fallback when the LLM API is unavailable.
    Confidence is capped at 0.80 since there is no LLM reasoning.
    """
    score = rule_result.score

    # Rules verdict (same thresholds as eval/run_eval.py and the Trust Receipt)
    if score >= 0.55:
        rules_verdict = "scam"
    elif score >= 0.25:
        rules_verdict = "suspicious"
    else:
        rules_verdict = "safe"

    # Each detector votes independently; the more severe verdict wins.
    # (A weighted average capped the classifier's influence at 0.4, so it could
    # never produce a "scam" verdict on its own when no rule matched.)
    verdict = rules_verdict
    combined = score if rules_verdict != "safe" else 1.0 - score
    if classifier_proba:
        clf_verdict = max(_SEVERITY, key=lambda c: classifier_proba.get(c, 0.0))
        clf_conf = classifier_proba.get(clf_verdict, 0.0)
        if _SEVERITY[clf_verdict] > _SEVERITY[rules_verdict]:
            verdict, combined = clf_verdict, clf_conf
        elif clf_verdict == rules_verdict:
            combined = max(combined, clf_conf)

    # Build simple red flags from rule matches (no LLM quoting)
    red_flags = []
    seen_cats = set()
    for match in rule_result.matches[:5]:  # top 5 rules
        if match.category not in seen_cats:
            red_flags.append(RedFlag(
                flag=match.name,
                quote_from_message=match.matched_text,
                why_it_matters=_category_explanation(match.category),
            ))
            seen_cats.add(match.category)

    what_to_do = _default_what_to_do(verdict)

    return ScamVerdict(
        verdict=verdict,
        confidence=min(0.80, combined),
        red_flags=red_flags,
        what_to_do=what_to_do,
        claims=[],
    )


def _category_explanation(category: str) -> str:
    explanations = {
        "otp_request": "No legitimate bank or company will ever ask for your OTP or PIN.",
        "collect_request": "You never need to enter your UPI PIN to receive money. This is a debit request.",
        "urgency": "Scammers create artificial urgency to stop you from thinking clearly.",
        "kyc_fraud": "Banks never ask you to complete KYC via SMS links or by sharing OTP.",
        "phishing_link": "This link does not appear to be an official bank or government website.",
        "lottery_scam": "You cannot win a lottery or prize you never entered.",
        "job_scam": "Legitimate employers never charge a registration or joining fee.",
        "impersonation": "RBI, NPCI, and police do not contact people via SMS to demand payments.",
        "remote_access": "Never install remote-access apps at the request of an unsolicited caller.",
        "fee_to_receive": "Legitimate refunds and prizes are never conditional on paying a fee first.",
        "suspicious_vpa": "Scammers use UPI IDs with words like 'refund', 'prize', or 'claim'.",
    }
    return explanations.get(category, "This pattern is commonly seen in financial scams.")


def _default_what_to_do(verdict: str) -> list[str]:
    if verdict == "scam":
        return [
            "Do not click any links or share any OTP, PIN, or personal details.",
            "Block the sender immediately.",
            "Report at cybercrime.gov.in or call 1930 (National Cyber Crime helpline).",
            "If money was transferred, call your bank's fraud helpline immediately.",
        ]
    elif verdict == "suspicious":
        return [
            "Treat with caution — do not act on the message immediately.",
            "Verify by calling the official number on your bank card or the company's official website.",
            "Do not share any OTP or PIN.",
            "Report at cybercrime.gov.in if you believe it is a scam.",
        ]
    else:
        return [
            "This message appears safe, but always verify before acting.",
            "Never share OTP or PIN with anyone, including bank staff.",
        ]


# ---------------------------------------------------------------------------
# LLM judge
# ---------------------------------------------------------------------------

def run_llm_judge(
    message: str,
    rule_result: RulesResult,
    classifier_proba: Optional[dict],
    advisory_context: str,
    adapter,
) -> ScamVerdict:
    """Call the LLM to produce a structured scam verdict.

    Args:
        message: Original SMS/WhatsApp text.
        rule_result: Output from rules.run_rules().
        classifier_proba: dict from classifier.predict_proba(), or None.
        advisory_context: Formatted KB passages from retriever.retrieve_as_context().
        adapter: LLM adapter instance.

    Returns:
        ScamVerdict. Falls back to rules_only_verdict on any LLM error.
    """
    from llm.prompts import SCAM_JUDGE_PROMPT_V1

    # Build rule hits summary for the prompt
    if rule_result.matches:
        rule_hits = "; ".join(
            f"{m.name} (matched: '{m.matched_text}')"
            for m in rule_result.matches[:8]
        )
    else:
        rule_hits = "No rules matched."

    clf_prob_str = (
        f"scam={classifier_proba.get('scam', 0):.2f}, "
        f"suspicious={classifier_proba.get('suspicious', 0):.2f}, "
        f"safe={classifier_proba.get('safe', 0):.2f}"
        if classifier_proba else "Not available."
    )

    prompt = SCAM_JUDGE_PROMPT_V1.format(
        rule_hits=rule_hits,
        classifier_prob=clf_prob_str,
        advisory_passages=advisory_context or "(No advisory passages available.)",
        message=message,
    )

    try:
        verdict: ScamVerdict = adapter.generate(
            prompt=prompt,
            response_schema=ScamVerdict,
            temperature=0.1,
        )
        logger.info("LLM verdict: %s (confidence=%.2f)", verdict.verdict, verdict.confidence)
        return verdict
    except Exception as exc:
        logger.warning("LLM judge failed (%s) — using rules-only fallback.", exc)
        return rules_only_verdict(rule_result, classifier_proba)
