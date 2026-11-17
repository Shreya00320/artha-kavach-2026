"""
core/goals.py — Goal planning, SIP, EMI and emergency-fund maths (plain Python, no AI).

Conventions: returns and interest rates are ANNUAL percentages (e.g. 12 for 12%),
compounded monthly — the convention Indian SIP and EMI calculators use.

Public API:
  sip_future_value(monthly, annual_return_pct, months) -> float
  sip_required(goal, annual_return_pct, months, current_savings=0) -> float
  months_to_goal(goal, monthly, annual_return_pct, current_savings=0) -> int | None
  emi(principal, annual_rate_pct, months) -> float
  loan_summary(principal, annual_rate_pct, months) -> dict
  prepayment_impact(principal, annual_rate_pct, months, extra_monthly) -> dict
  emergency_fund(monthly_essentials, months_cover=6, current=0) -> dict
  inflate(amount, years, inflation_pct=6) -> float
  Goal / plan_goals(goals, monthly_surplus, annual_return_pct)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional


def _r(annual_pct: float) -> float:
    return annual_pct / 100 / 12


# ---------------------------------------------------------------------------
# SIP / savings growth
# ---------------------------------------------------------------------------

def sip_future_value(monthly: float, annual_return_pct: float, months: int) -> float:
    """Future value of a monthly SIP invested at the start of each month."""
    if months <= 0 or monthly <= 0:
        return 0.0
    r = _r(annual_return_pct)
    if r == 0:
        return round(monthly * months, 2)
    return round(monthly * ((1 + r) ** months - 1) / r * (1 + r), 2)


def lump_sum_future_value(amount: float, annual_return_pct: float, months: int) -> float:
    return round(amount * (1 + _r(annual_return_pct)) ** max(months, 0), 2)


def sip_required(goal: float, annual_return_pct: float, months: int, current_savings: float = 0.0) -> float:
    """Monthly SIP needed to reach `goal` in `months`, counting growth on what you already have."""
    if months <= 0:
        raise ValueError("months must be positive")
    remaining = goal - lump_sum_future_value(current_savings, annual_return_pct, months)
    if remaining <= 0:
        return 0.0
    r = _r(annual_return_pct)
    if r == 0:
        return round(remaining / months, 2)
    return round(remaining * r / (((1 + r) ** months - 1) * (1 + r)), 2)


def months_to_goal(goal: float, monthly: float, annual_return_pct: float,
                   current_savings: float = 0.0, max_months: int = 600) -> Optional[int]:
    """Months until savings reach `goal` (None if not within max_months)."""
    if current_savings >= goal:
        return 0
    if monthly <= 0 and annual_return_pct <= 0:
        return None
    r = _r(annual_return_pct)
    balance = current_savings
    for m in range(1, max_months + 1):
        balance = (balance + monthly) * (1 + r)
        if balance >= goal:
            return m
    return None


def inflate(amount: float, years: float, inflation_pct: float = 6.0) -> float:
    """Future cost of something that costs `amount` today."""
    return round(amount * (1 + inflation_pct / 100) ** years, 2)


# ---------------------------------------------------------------------------
# Loans / EMI
# ---------------------------------------------------------------------------

def emi(principal: float, annual_rate_pct: float, months: int) -> float:
    """Standard reducing-balance EMI."""
    if months <= 0:
        raise ValueError("months must be positive")
    r = _r(annual_rate_pct)
    if r == 0:
        return round(principal / months, 2)
    f = (1 + r) ** months
    return round(principal * r * f / (f - 1), 2)


def loan_summary(principal: float, annual_rate_pct: float, months: int) -> dict:
    e = emi(principal, annual_rate_pct, months)
    total = e * months
    return {
        "emi": e,
        "total_payment": round(total, 2),
        "total_interest": round(total - principal, 2),
        "interest_share_pct": round((total - principal) / total * 100, 1) if total else 0.0,
    }


def prepayment_impact(principal: float, annual_rate_pct: float, months: int, extra_monthly: float) -> dict:
    """Effect of paying `extra_monthly` on top of the EMI every month."""
    base = loan_summary(principal, annual_rate_pct, months)
    e, r = base["emi"], _r(annual_rate_pct)
    bal, paid, n = principal, 0.0, 0
    while bal > 0.005 and n < months:
        interest = bal * r
        pay = min(e + extra_monthly, bal + interest)
        bal = bal + interest - pay
        paid += pay
        n += 1
    interest_paid = paid - principal
    return {
        "months_original": months,
        "months_with_prepayment": n,
        "months_saved": months - n,
        "interest_original": base["total_interest"],
        "interest_with_prepayment": round(interest_paid, 2),
        "interest_saved": round(base["total_interest"] - interest_paid, 2),
    }


# ---------------------------------------------------------------------------
# Emergency fund
# ---------------------------------------------------------------------------

def emergency_fund(monthly_essentials: float, months_cover: int = 6, current: float = 0.0) -> dict:
    target = round(monthly_essentials * months_cover, 2)
    gap = max(target - current, 0.0)
    return {
        "target": target,
        "current": round(current, 2),
        "gap": round(gap, 2),
        "progress_pct": round(min(current / target, 1.0) * 100, 1) if target else 100.0,
        "months_cover_now": round(current / monthly_essentials, 1) if monthly_essentials else 0.0,
    }


# ---------------------------------------------------------------------------
# Multiple goals
# ---------------------------------------------------------------------------

@dataclass
class Goal:
    name: str
    target: float          # amount needed (in today's rupees)
    months: int            # time horizon
    saved: float = 0.0     # already set aside
    priority: int = 1      # 1 = highest
    inflation_pct: float = 0.0   # set >0 for long-horizon goals (education, house)


def plan_goals(goals: list[Goal], monthly_surplus: float, annual_return_pct: float = 7.0) -> dict:
    """Monthly amount each goal needs, funded in priority order from the surplus.

    Returns per-goal rows plus whether the surplus covers everything.
    """
    rows, remaining = [], max(monthly_surplus, 0.0)
    for g in sorted(goals, key=lambda g: (g.priority, g.months)):
        future_target = inflate(g.target, g.months / 12, g.inflation_pct) if g.inflation_pct else g.target
        need = sip_required(future_target, annual_return_pct, g.months, g.saved)
        funded = min(need, remaining)
        remaining -= funded
        eta = months_to_goal(future_target, funded, annual_return_pct, g.saved) if funded < need else g.months
        rows.append({
            "goal": g.name,
            "target_today": g.target,
            "target_at_deadline": future_target,
            "months": g.months,
            "monthly_needed": need,
            "monthly_funded": round(funded, 2),
            "on_track": funded + 0.01 >= need,
            "eta_months_at_funded_rate": eta,
            "progress_pct": round(min(g.saved / future_target, 1) * 100, 1) if future_target else 100.0,
        })
    total_needed = round(sum(r["monthly_needed"] for r in rows), 2)
    return {
        "rows": rows,
        "total_monthly_needed": total_needed,
        "monthly_surplus": round(monthly_surplus, 2),
        "shortfall": round(max(total_needed - monthly_surplus, 0.0), 2),
        "left_over": round(max(remaining, 0.0), 2),
    }


def years_months(m: Optional[int]) -> str:
    if m is None:
        return "not within 50 years"
    y, mm = divmod(int(m), 12)
    parts = ([f"{y} yr"] if y else []) + ([f"{mm} mo"] if mm else [])
    return " ".join(parts) or "0 mo"


def rule_of_72(annual_return_pct: float) -> float:
    """Approximate years to double money."""
    return round(72 / annual_return_pct, 1) if annual_return_pct > 0 else math.inf
