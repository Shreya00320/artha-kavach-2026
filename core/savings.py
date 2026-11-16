"""
core/savings.py — Step-up savings plan computation (pure Python, no LLM).

Based on the Save More Tomorrow (SMarT) behavioural-finance concept.
Labelled clearly as an illustration, not a financial guarantee.

Public API:
  flat_savings_plan(income, rate, months) -> SavingsPlan
  stepup_savings_plan(income, initial_rate, stepup_pct, raise_every_n, months) -> SavingsPlan
  compare_plans(income, goal, months, initial_rate, stepup_pct, raise_every_n) -> dict
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SavingsPlan:
    """Month-by-month savings plan."""
    label: str
    income: float
    months: int
    monthly_amounts: list[float]      # savings per month
    cumulative: list[float]           # running total
    total_saved: float
    final_rate_pct: float             # savings rate in final month
    disclaimer: str = (
        "This is a simplified illustration based on behavioural-finance research "
        "(Save More Tomorrow / SMarT). It does not account for inflation, "
        "investment returns, taxes, or unexpected expenses. Not financial advice."
    )


def flat_savings_plan(
    income: float,
    rate: float,       # e.g. 0.20 for 20%
    months: int = 12,
) -> SavingsPlan:
    """Save a fixed percentage of income every month.

    Args:
        income: Monthly take-home income (INR).
        rate: Savings rate as decimal (0.0 – 1.0).
        months: Planning horizon in months.

    Returns:
        SavingsPlan with month-by-month breakdown.
    """
    if income <= 0 or rate <= 0 or months <= 0:
        return SavingsPlan(
            label="Flat savings", income=income, months=months,
            monthly_amounts=[], cumulative=[], total_saved=0, final_rate_pct=0
        )

    monthly_save = round(income * rate, 2)
    monthly_amounts = [monthly_save] * months
    cumulative = []
    running = 0.0
    for amt in monthly_amounts:
        running += amt
        cumulative.append(round(running, 2))

    return SavingsPlan(
        label="Flat savings",
        income=income,
        months=months,
        monthly_amounts=monthly_amounts,
        cumulative=cumulative,
        total_saved=round(running, 2),
        final_rate_pct=round(rate * 100, 1),
    )


def stepup_savings_plan(
    income: float,
    initial_rate: float,     # e.g. 0.10 for 10%
    stepup_pct: float = 0.01,  # increase rate by this each raise (e.g. 0.01 = +1%)
    raise_every_n: int = 6,    # raise savings rate every N months
    months: int = 12,
) -> SavingsPlan:
    """Step-up plan: start lower, raise savings share at each income-review point.

    Models the Save More Tomorrow pattern where you pre-commit to saving
    more whenever your income increases.

    Args:
        income: Monthly income (assumed constant for illustration).
        initial_rate: Starting savings rate as decimal.
        stepup_pct: How much to increase the rate at each step (decimal).
        raise_every_n: Months between each rate step-up.
        months: Planning horizon.

    Returns:
        SavingsPlan with month-by-month breakdown.
    """
    if income <= 0 or months <= 0:
        return SavingsPlan(
            label="Step-up savings", income=income, months=months,
            monthly_amounts=[], cumulative=[], total_saved=0, final_rate_pct=0
        )

    monthly_amounts = []
    cumulative = []
    running = 0.0
    current_rate = initial_rate
    final_rate = initial_rate

    for month_idx in range(1, months + 1):
        # Step up rate at each interval (but not at month 1)
        if month_idx > 1 and (month_idx - 1) % raise_every_n == 0:
            current_rate = min(current_rate + stepup_pct, 1.0)
        amt = round(income * current_rate, 2)
        monthly_amounts.append(amt)
        running += amt
        cumulative.append(round(running, 2))
        final_rate = current_rate

    return SavingsPlan(
        label="Step-up savings (SMarT)",
        income=income,
        months=months,
        monthly_amounts=monthly_amounts,
        cumulative=cumulative,
        total_saved=round(running, 2),
        final_rate_pct=round(final_rate * 100, 1),
    )


def compare_plans(
    income: float,
    goal: float,
    months: int = 12,
    initial_rate: float = 0.10,
    stepup_pct: float = 0.01,
    raise_every_n: int = 6,
) -> dict:
    """Compare flat vs step-up savings plans against a savings goal.

    Args:
        income: Monthly take-home income (INR).
        goal: Savings target (INR).
        months: Planning horizon.
        initial_rate: Starting savings rate for step-up plan (also flat rate).
        stepup_pct: Rate increase per step in step-up plan.
        raise_every_n: Months between step-ups.

    Returns:
        dict with flat_plan, stepup_plan, goal, goal_met_flat_month,
        goal_met_stepup_month, stepup_advantage_inr.
    """
    flat = flat_savings_plan(income, initial_rate, months)
    stepup = stepup_savings_plan(income, initial_rate, stepup_pct, raise_every_n, months)

    def _month_goal_met(plan: SavingsPlan) -> int | None:
        for i, cum in enumerate(plan.cumulative, 1):
            if cum >= goal:
                return i
        return None

    flat_month = _month_goal_met(flat)
    stepup_month = _month_goal_met(stepup)
    advantage = round(stepup.total_saved - flat.total_saved, 2)

    return {
        "flat_plan": flat,
        "stepup_plan": stepup,
        "goal": goal,
        "goal_met_flat_month": flat_month,
        "goal_met_stepup_month": stepup_month,
        "stepup_advantage_inr": advantage,
        "disclaimer": flat.disclaimer,
    }
