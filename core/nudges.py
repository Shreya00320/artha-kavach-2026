"""
core/nudges.py — Financial nudge generator.

Strategy:
  1. LLM writes nudges based ONLY on engine-computed numbers.
  2. Post-check: reject any nudge containing a number not in engine output.
  3. Fallback to rule-based template nudges (no LLM) if LLM fails or all nudges rejected.

SPEC rule: "any number in [the LLM's] text must appear in the engine output
(add a post-check that rejects nudges containing numbers not in the engine data)"

Public API:
  generate_nudges(summary, adapter=None) -> list[dict]
  rule_based_nudges(summary) -> list[dict]
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.budget_engine import BudgetSummary

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Number extraction helpers
# ---------------------------------------------------------------------------

def _extract_numbers(text: str) -> set[float]:
    """Extract all numeric values from a string (handles commas, Rs prefix)."""
    # Strip Rs/₹ and commas, find all floats/ints
    cleaned = text.replace(",", "").replace("Rs", "").replace("₹", "")
    matches = re.findall(r"\b\d+(?:\.\d+)?\b", cleaned)
    return {float(m) for m in matches}


def _get_summary_numbers(summary: "BudgetSummary") -> set[float]:
    """Collect all numeric values in the budget summary."""
    nums: set[float] = set()

    def _add(v):
        if isinstance(v, (int, float)) and v != 0:
            nums.add(float(v))

    _add(summary.total_income)
    _add(summary.total_expense)
    _add(summary.net)
    _add(summary.savings_rate)
    _add(summary.needs_total)
    _add(summary.wants_total)
    _add(summary.savings_total)
    _add(summary.needs_pct)
    _add(summary.wants_pct)
    _add(summary.savings_pct)
    _add(summary.needs_target)
    _add(summary.wants_target)
    _add(summary.savings_target)
    _add(abs(summary.needs_delta))
    _add(abs(summary.wants_delta))
    _add(abs(summary.savings_delta))
    for v in summary.by_category.values():
        _add(v)

    # Also add rounded versions (100-precision) to allow minor rounding
    extras = set()
    for n in nums:
        extras.add(round(n, 0))
        extras.add(round(n, 1))
    nums |= extras

    return nums


def _number_in_summary(number: float, summary_nums: set[float]) -> bool:
    """Check if a number appears in the summary (with ±1% tolerance for rounding)."""
    if number in summary_nums:
        return True
    for snum in summary_nums:
        if snum > 0 and abs(number - snum) / snum < 0.01:
            return True
    return False


def _verify_nudges(nudges: list[dict], summary: "BudgetSummary") -> list[dict]:
    """Remove nudges that contain numbers NOT in the engine summary.

    Returns the filtered list of valid nudges.
    """
    summary_nums = _get_summary_numbers(summary)
    valid = []
    for nudge in nudges:
        text = nudge.get("text", "")
        nudge_nums = _extract_numbers(text)
        # Allow percentages that could combine category pcts (summable) but strictly
        # check each isolated number
        invalid = {n for n in nudge_nums if not _number_in_summary(n, summary_nums)}
        if invalid:
            logger.warning("Rejecting nudge with invented numbers %s: %r", invalid, text)
        else:
            valid.append(nudge)
    return valid


# ---------------------------------------------------------------------------
# Rule-based fallback nudges
# ---------------------------------------------------------------------------

def rule_based_nudges(summary: "BudgetSummary") -> list[dict]:
    """Generate template nudges from engine numbers. No LLM. Always safe."""
    nudges = []

    # 1. Savings rate nudge
    if summary.total_income > 0:
        sr = summary.savings_rate
        if sr >= 20:
            nudges.append({
                "text": f"Great job! You saved {sr}% of your income this month — above the 20% target.",
                "category": "Savings_Investment",
                "type": "positive",
            })
        elif sr >= 10:
            nudges.append({
                "text": f"Your savings rate is {sr}%. Nudging it to 20% would add Rs {round((0.20 - sr/100) * summary.total_income)} more per month.",
                "category": "Savings_Investment",
                "type": "suggestion",
            })
        else:
            nudges.append({
                "text": f"Your savings rate is {sr}%. Even Rs {round(summary.total_income * 0.10)} per month (10%) would build a strong habit.",
                "category": "Savings_Investment",
                "type": "suggestion",
            })

    # 2. Biggest spend category
    if summary.by_category:
        top_cat, top_amt = max(summary.by_category.items(), key=lambda x: x[1])
        nudges.append({
            "text": f"Your biggest spend this period: {top_cat} at Rs {round(top_amt)}. Worth reviewing?",
            "category": top_cat,
            "type": "suggestion",
        })

    # 3. Wants over-budget nudge
    if summary.wants_delta > 0 and summary.wants_target > 0:
        nudges.append({
            "text": f"Wants spending is Rs {round(summary.wants_delta)} over the 30% budget target of Rs {round(summary.wants_target)}.",
            "category": "Shopping",
            "type": "warning",
        })
    elif summary.needs_delta > 0 and summary.needs_target > 0:
        nudges.append({
            "text": f"Needs spending at Rs {round(summary.needs_total)} is Rs {round(summary.needs_delta)} above the 50% target.",
            "category": "Food",
            "type": "warning",
        })

    # Return up to 3 non-duplicate nudges
    return nudges[:3]


# ---------------------------------------------------------------------------
# LLM nudge generation with verification
# ---------------------------------------------------------------------------

def _build_engine_summary_text(summary: "BudgetSummary") -> str:
    """Build a concise text summary of budget numbers for the LLM prompt."""
    lines = [
        f"Period: {summary.period_start} to {summary.period_end} ({summary.days_covered} days)",
        f"Income: Rs {summary.total_income}",
        f"Total expense: Rs {summary.total_expense}",
        f"Net (income - expense): Rs {summary.net}",
        f"Savings rate: {summary.savings_rate}%",
        "",
        "Spending by category:",
    ]
    for cat, amt in sorted(summary.by_category.items(), key=lambda x: -x[1]):
        lines.append(f"  {cat}: Rs {round(amt, 2)}")
    lines += [
        "",
        "50/30/20 breakdown:",
        f"  Needs: Rs {summary.needs_total} ({summary.needs_pct}% of income, target Rs {summary.needs_target})",
        f"  Wants: Rs {summary.wants_total} ({summary.wants_pct}% of income, target Rs {summary.wants_target})",
        f"  Savings: Rs {summary.savings_total} ({summary.savings_pct}% of income, target Rs {summary.savings_target})",
        f"  Needs delta (over/under target): Rs {summary.needs_delta}",
        f"  Wants delta: Rs {summary.wants_delta}",
        f"  Savings delta: Rs {summary.savings_delta}",
    ]
    return "\n".join(lines)


def generate_nudges(
    summary: "BudgetSummary",
    adapter=None,
) -> list[dict]:
    """Generate 2-3 financial nudges.

    Args:
        summary: Budget summary from compute_budget().
        adapter: LLM adapter. If None, uses rule-based nudges only.

    Returns:
        list of nudge dicts with keys: text, category, type.
    """
    if adapter is None:
        logger.info("No adapter provided; using rule-based nudges.")
        return rule_based_nudges(summary)

    from llm.prompts import NUDGE_PROMPT_V1
    from llm.schemas import NudgeListLLM

    engine_text = _build_engine_summary_text(summary)
    prompt = NUDGE_PROMPT_V1.format(engine_summary=engine_text)

    try:
        result: NudgeListLLM = adapter.generate(
            prompt=prompt,
            response_schema=NudgeListLLM,
            temperature=0.3,
        )
        nudges_raw = [n.model_dump() for n in result.nudges]
        verified = _verify_nudges(nudges_raw, summary)
        if verified:
            logger.info("LLM nudges: %d generated, %d passed verification.", len(nudges_raw), len(verified))
            return verified
        else:
            logger.warning("All LLM nudges failed verification; falling back to rule-based.")
            return rule_based_nudges(summary)
    except Exception as exc:
        logger.warning("LLM nudge generation failed: %s — using rule-based fallback.", exc)
        return rule_based_nudges(summary)
