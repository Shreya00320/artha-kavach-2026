"""
core/assistant.py — "Ask Artha": a money chat grounded in the user's own numbers.

Design (same principle as nudges.py — numbers come from code, never from the LLM):
  1. build_facts() computes a labelled fact sheet from the budget engine output.
  2. A rules engine answers common questions directly from those facts
     ("how much did I spend on food?", "can I afford ₹15,000?", "where can I cut?").
  3. If an LLM adapter is available, the LLM may phrase an answer, but ONLY from
     the fact sheet; a post-check rejects any reply containing a number that is
     not in the facts or the question, and we fall back to the rules answer.

Public API:
  build_facts(summary, txns, subscriptions=None) -> dict[str, float | str]
  answer_question(question, summary, txns, adapter=None) -> Answer
  SUGGESTED_QUESTIONS
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from core.nudges import _extract_numbers, _number_in_summary

logger = logging.getLogger(__name__)

SUGGESTED_QUESTIONS = [
    "How much did I spend on food?",
    "Where can I cut back?",
    "Can I afford a ₹15,000 phone this month?",
    "What subscriptions am I paying for?",
    "What's my savings rate?",
    "How big should my emergency fund be?",
]

CATEGORY_WORDS = {
    "Food": r"food|eat|eating|swiggy|zomato|restaurant|grocer|khana|blinkit|zepto|dining|chai|coffee",
    "Transport": r"transport|travel|cab|uber|ola|rapido|auto|fuel|petrol|metro|commute|train|flight",
    "Shopping": r"shopping|amazon|flipkart|myntra|clothes|shop|meesho",
    "Entertainment": r"entertainment|movie|netflix|ott|spotify|hotstar|fun|party|gaming",
    "Utilities": r"utilit|bill|electricity|recharge|internet|wifi|gas|water|phone bill",
    "Healthcare": r"health|medical|doctor|medicine|pharmacy|gym|fitness|hospital",
    "Education": r"education|course|fees|tuition|books|study|udemy",
    "Rent": r"rent|pg|house|flat|hostel",
    "EMI_Loan": r"emi|loan|debt|credit",
    "Savings_Investment": r"sip|invest|mutual fund|savings?\b|lic|insurance|ppf|nps",
    "ATM": r"atm|cash",
}


@dataclass
class Answer:
    text: str
    method: str                      # "rules" | "llm"
    facts_used: list[str] = field(default_factory=list)


def _inr(x: float) -> str:
    return f"₹{x:,.0f}"


def build_facts(summary, txns, subscriptions=None) -> dict:
    """Labelled facts (all computed in code) the assistant may quote."""
    f: dict = {
        "period": f"{summary.period_start} to {summary.period_end}",
        "income": summary.total_income,
        "spending": summary.total_expense,
        "left_over (income - spending)": summary.net,
        "savings_rate_pct": summary.savings_rate,
        "needs_spend": summary.needs_total,
        "wants_spend": summary.wants_total,
        "savings_investment_spend": summary.savings_total,
        "needs_target_50pct": summary.needs_target,
        "wants_target_30pct": summary.wants_target,
        "savings_target_20pct": summary.savings_target,
        "wants_budget_remaining": round(summary.wants_target - summary.wants_total, 2),
        "transfers_to_people": getattr(summary, "transfers_out", 0.0),
        "refunds": getattr(summary, "refunds_total", 0.0),
        "emergency_fund_target_6_months_of_needs": round(summary.needs_total * 6, 2),
    }
    for cat, amt in sorted(summary.by_category.items(), key=lambda kv: -kv[1]):
        f[f"category:{cat}"] = round(amt, 2)
    if subscriptions:
        f["subscriptions_monthly_total"] = round(sum(s.monthly_amount for s in subscriptions), 2)
        f["subscriptions_annual_total"] = round(sum(s.annual_cost for s in subscriptions), 2)
        for s in subscriptions[:8]:
            f[f"subscription:{s.merchant}"] = s.monthly_amount
    return f


def _facts_text(facts: dict) -> str:
    out = []
    for k, v in facts.items():
        out.append(f"- {k}: {_inr(v) if isinstance(v, (int, float)) and not k.endswith('_pct') else v}")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Rules answers
# ---------------------------------------------------------------------------

def _amount_in(question: str) -> Optional[float]:
    q = question.lower().replace(",", "")
    m = re.search(r"(?:₹|rs\.?|inr)\s*(\d+(?:\.\d+)?)\s*(k|lakh|l)?\b|(\d+(?:\.\d+)?)\s*(k|lakh|rupees|rs)\b", q)
    if not m:
        return None
    num = float(m.group(1) or m.group(3))
    unit = (m.group(2) or m.group(4) or "").lower()
    if unit == "k":
        num *= 1_000
    elif unit in ("lakh", "l"):
        num *= 100_000
    return num


def _category_in(question: str) -> Optional[str]:
    q = question.lower()
    for cat, pat in CATEGORY_WORDS.items():
        if re.search(rf"\b({pat})", q):
            return cat
    return None


def _merchant_total(question: str, txns) -> Optional[tuple[str, float, int]]:
    q = question.lower()
    totals: dict[str, list[float]] = {}
    for t in txns:
        if t.transaction_type == "debit" and t.merchant and t.parse_method != "failed":
            totals.setdefault(t.merchant.lower(), []).append(t.amount or 0)
    for name in sorted(totals, key=len, reverse=True):
        if len(name) >= 3 and re.search(rf"\b{re.escape(name)}\b", q):
            return name, sum(totals[name]), len(totals[name])
    return None


def rules_answer(question: str, summary, txns, subscriptions=None) -> Answer:
    q = question.lower().strip()
    facts_used: list[str] = []
    s = summary

    if not s.n_parsed and not s.total_expense:
        return Answer("I don't have any transactions yet. Load your bank SMS or the sample data in "
                      "Smart Budget, then ask me again.", "rules")

    # Affordability
    amount = _amount_in(q)
    if amount and re.search(r"afford|buy|purchase|spend .* on|can i|should i", q):
        left = s.net
        wants_left = s.wants_target - s.wants_total
        facts_used += ["left_over (income - spending)", "wants_budget_remaining"]
        if s.total_income <= 0:
            return Answer(f"I can't see any income in this period, so I can't judge {_inr(amount)} safely. "
                          f"You've spent {_inr(s.total_expense)} so far.", "rules", ["spending"])
        if amount <= wants_left:
            verdict = (f"Yes — {_inr(amount)} fits inside what's left of your 30% 'wants' budget "
                       f"({_inr(wants_left)} remaining).")
        elif amount <= left:
            verdict = (f"Possible, but it goes past your 'wants' budget ({_inr(max(wants_left, 0))} left). "
                       f"You have {_inr(left)} left over this period, so it would come out of savings.")
        else:
            verdict = (f"Not comfortably — {_inr(amount)} is more than the {_inr(max(left, 0))} you have left "
                       f"over this period. Consider saving towards it in the Goals tab.")
        return Answer(verdict, "rules", facts_used)

    # Subscriptions
    if re.search(r"subscri|ott|recurring|autopay|mandate", q):
        if not subscriptions:
            return Answer("I didn't find any subscriptions in this data.", "rules")
        lines = [f"- {x.merchant}: {_inr(x.monthly_amount)}/month ({_inr(x.annual_cost)}/year)" for x in subscriptions[:8]]
        total_m = sum(x.monthly_amount for x in subscriptions)
        total_y = sum(x.annual_cost for x in subscriptions)
        return Answer(f"You're paying for {len(subscriptions)} subscription(s), about {_inr(total_m)} a month "
                      f"or {_inr(total_y)} a year:\n" + "\n".join(lines) +
                      "\n\nCancel the ones you haven't used in the last month.", "rules",
                      ["subscriptions_monthly_total", "subscriptions_annual_total"])

    # Where to cut
    if re.search(r"\bcut\b|reduce|save more|spend less|overspend|cut back|kam", q):
        wants = {k: v for k, v in s.by_category.items()
                 if k in ("Food", "Shopping", "Entertainment", "Transport", "Other") and v > 0}
        top = sorted(wants.items(), key=lambda kv: -kv[1])[:3]
        parts = [f"{k} ({_inr(v)})" for k, v in top]
        msg = f"Your biggest flexible categories are {', '.join(parts)}." if parts else ""
        if s.wants_delta > 0:
            msg += f" 'Wants' are {_inr(s.wants_delta)} over the 30% guideline."
        if subscriptions:
            msg += f" Subscriptions add up to {_inr(sum(x.monthly_amount for x in subscriptions))} a month — an easy place to start."
        msg += " Trimming the top category by a tenth is usually painless."
        return Answer(msg.strip(), "rules", [f"category:{k}" for k, _ in top])

    # Savings
    if re.search(r"saving rate|savings rate|how much (did|have) i sav|am i saving|save\b", q):
        msg = (f"You kept {_inr(s.net)} of {_inr(s.total_income)} income — a savings rate of {s.savings_rate}%. "
               f"The 50/30/20 guideline suggests at least {_inr(s.savings_target)}.")
        if s.savings_total:
            msg += f" You also put {_inr(s.savings_total)} into SIPs/insurance/investments."
        return Answer(msg, "rules", ["savings_rate_pct", "left_over (income - spending)"])

    # Emergency fund
    if re.search(r"emergency", q):
        target = round(s.needs_total * 6, 2)
        return Answer(f"Aim for 6 months of essential costs. Your 'needs' this period were {_inr(s.needs_total)}, "
                      f"so a target of about {_inr(target)}. Build it in a savings account or liquid fund — "
                      f"see the Goals tab for a monthly plan.", "rules", ["emergency_fund_target_6_months_of_needs"])

    # Income
    if re.search(r"income|salary|earn|kamai", q):
        return Answer(f"Income detected this period: {_inr(s.total_income)}"
                      + (f" (plus {_inr(s.transfers_in)} received from people, not counted as income)." if getattr(s, "transfers_in", 0) else "."),
                      "rules", ["income"])

    # Transfers
    if re.search(r"transfer|sent to (friends|people|family)|p2p", q):
        return Answer(f"You sent {_inr(getattr(s, 'transfers_out', 0))} to people/own accounts. "
                      f"These are kept out of spending so they don't distort your budget.", "rules",
                      ["transfers_to_people"])

    # Specific merchant
    mt = _merchant_total(q, txns)
    if mt and re.search(r"spen|kharch|paid|pay|how much", q):
        name, total, n = mt
        return Answer(f"You paid {name.title()} {_inr(total)} across {n} transaction(s).", "rules")

    # Category spend
    cat = _category_in(q)
    if cat and re.search(r"spen|kharch|how much|total|cost", q):
        amt = s.by_category.get(cat, 0.0)
        share = amt / s.total_expense * 100 if s.total_expense else 0
        return Answer(f"You spent {_inr(amt)} on {cat.replace('_', ' / ')} — {share:.0f}% of your spending "
                      f"({_inr(s.total_expense)}) between {s.period_start} and {s.period_end}.",
                      "rules", [f"category:{cat}", "spending"])

    # Biggest categories
    if re.search(r"most|biggest|top|where.*(money|spend)|kahan", q):
        top = sorted(((k, v) for k, v in s.by_category.items() if v > 0), key=lambda kv: -kv[1])[:3]
        return Answer("Your top spending categories: " + ", ".join(f"{k} {_inr(v)}" for k, v in top) + ".",
                      "rules", [f"category:{k}" for k, _ in top])

    # Overview
    return Answer(
        f"Between {s.period_start} and {s.period_end}: income {_inr(s.total_income)}, spending "
        f"{_inr(s.total_expense)}, left over {_inr(s.net)} ({s.savings_rate}% savings rate). "
        "Try asking: " + "; ".join(SUGGESTED_QUESTIONS[:3]),
        "rules", ["income", "spending", "left_over (income - spending)"],
    )


# ---------------------------------------------------------------------------
# LLM path with number post-check
# ---------------------------------------------------------------------------

def _allowed_numbers(facts: dict, question: str) -> set[float]:
    nums: set[float] = set()
    for v in facts.values():
        if isinstance(v, (int, float)):
            for x in (v, abs(v)):
                nums |= {float(x), round(float(x), 0), round(float(x), 1)}
    nums |= _extract_numbers(question)
    nums |= {50.0, 30.0, 20.0, 6.0, 12.0, 1930.0}   # guideline constants we explain
    return nums


def verify_numbers(text: str, facts: dict, question: str) -> set[float]:
    """Numbers in `text` that are not backed by the facts or the question."""
    allowed = _allowed_numbers(facts, question)
    return {n for n in _extract_numbers(text) if n > 1 and not _number_in_summary(n, allowed)}


def answer_question(question: str, summary, txns, adapter=None, subscriptions=None) -> Answer:
    rules = rules_answer(question, summary, txns, subscriptions)
    if adapter is None:
        return rules

    from llm.prompts import ASSISTANT_PROMPT_V1
    from llm.schemas import AssistantAnswerLLM

    facts = build_facts(summary, txns, subscriptions)
    prompt = ASSISTANT_PROMPT_V1.format(facts=_facts_text(facts), question=question.strip()[:500],
                                        draft=rules.text)
    try:
        out: AssistantAnswerLLM = adapter.generate(prompt=prompt, response_schema=AssistantAnswerLLM,
                                                   temperature=0.2)
        bad = verify_numbers(out.answer, facts, question)
        if bad:
            logger.warning("Assistant answer had unbacked numbers %s — using rules answer.", bad)
            return rules
        return Answer(out.answer.strip(), "llm", out.facts_used or rules.facts_used)
    except Exception as exc:
        logger.warning("Assistant LLM failed (%s) — using rules answer.", exc)
        return rules
