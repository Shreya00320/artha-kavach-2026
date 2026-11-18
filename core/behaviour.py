"""core/behaviour.py – behavioural-finance nudges, computed from engine numbers only.

Ideas: "life energy" cost of spending (Dominguez & Robin), pay-yourself-first default
(Thaler & Sunstein). Every figure is plain arithmetic on the BudgetSummary; the only
assumption is a 160-hour working month (8h x 20 days), shown to the user.

  hours_of_work(amount, monthly_income) -> float | None
  behavioural_nudges(summary) -> list[dict]
"""

from __future__ import annotations

from core.budget_engine import NEEDS_CATEGORIES, SAVINGS_CATEGORIES

WORK_HOURS_PER_MONTH = 160


def hours_of_work(amount: float, monthly_income: float):
    """Hours of work needed to earn `amount`, or None if income unknown."""
    if monthly_income <= 0 or amount <= 0:
        return None
    return amount / (monthly_income / WORK_HOURS_PER_MONTH)


def behavioural_nudges(summary) -> list[dict]:
    out: list[dict] = []
    income = summary.total_income
    if income <= 0:
        return out

    wants = {k: v for k, v in summary.by_category.items()
             if k not in NEEDS_CATEGORIES and k not in SAVINGS_CATEGORIES and v > 0
             and k not in ("Salary", "Transfer", "Refund")}
    if wants:
        cat, amt = max(wants.items(), key=lambda kv: kv[1])
        h = hours_of_work(amt, income)
        out.append({
            "text": (f"⏱️ Your biggest 'want' is {cat}: Rs {round(amt):,} — that is about "
                     f"{round(h)} hours of your work (assuming a {WORK_HOURS_PER_MONTH}-hour month). "
                     f"Worth it?"),
            "category": cat, "type": "suggestion",
        })

    if summary.savings_rate < 20:
        pay_first = round(income * 0.10)
        out.append({
            "text": (f"🏦 Pay yourself first: the day your salary arrives, move Rs {pay_first:,} "
                     f"(10% of Rs {round(income):,}) to savings before spending. "
                     f"Automating it removes the willpower step."),
            "category": "Savings_Investment", "type": "suggestion",
        })
    return out
