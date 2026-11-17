"""
core/budget_engine.py — Pure Python budget computation engine.

No LLM calls. All arithmetic done here and results passed to nudge writer.

Public API:
  compute_budget(txns, income=None) -> BudgetSummary
  detect_recurring(txns) -> list[RecurringPayment]
  compute_pace(txns, today=None) -> dict  # projected month-end spend
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

from core.categoriser import CategorisedTransaction

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 50/30/20 category mapping
# ---------------------------------------------------------------------------

NEEDS_CATEGORIES = {"Rent", "EMI_Loan", "Utilities", "Healthcare", "Education", "Food"}
SAVINGS_CATEGORIES = {"Savings_Investment"}
WANTS_CATEGORIES = {
    "Transport", "Shopping", "Entertainment", "Transfer", "ATM", "Other", "Refund"
}
# "Refund" holds a NEGATIVE amount (money back from purchases) and nets off Wants.
# "Transfer" (money to people / own accounts / card bills) is excluded from spending
# by default and reported separately as transfers_out.
# Salary/income is not a spend category

# ---------------------------------------------------------------------------
# Output models
# ---------------------------------------------------------------------------

@dataclass
class RecurringPayment:
    """A detected recurring payment pattern."""
    merchant: str
    category: str
    typical_amount: float       # median amount
    occurrences: int            # number of times detected
    months: list[str]           # e.g. ["2026-10", "2026-11"]


@dataclass
class BudgetSummary:
    """Complete monthly budget summary with 50/30/20 breakdown."""
    # Period
    period_start: Optional[str]   # YYYY-MM-DD of earliest txn
    period_end: Optional[str]     # YYYY-MM-DD of latest txn
    days_covered: int

    # Raw totals
    total_income: float           # sum of all credits (Salary category)
    total_expense: float          # sum of all debits
    net: float                    # income - expense
    savings_rate: float           # net / income, or 0 if no income

    # By category
    by_category: dict[str, float]      # category -> total spent

    # 50/30/20
    needs_total: float
    wants_total: float
    savings_total: float
    needs_pct: float              # pct of income (or expense if no income)
    wants_pct: float
    savings_pct: float

    # Suggested 50/30/20 targets (from income)
    needs_target: float
    wants_target: float
    savings_target: float

    # Over/under budget per bucket
    needs_delta: float            # positive = over needs target
    wants_delta: float
    savings_delta: float          # positive = above savings target (good!)

    # Recurring payments detected
    recurring: list[RecurringPayment] = field(default_factory=list)

    # Pace projection
    pace: dict = field(default_factory=dict)   # see compute_pace()

    # Metadata
    n_transactions: int = 0
    n_parsed: int = 0
    n_failed: int = 0

    # Money moved that is not category spending
    transfers_out: float = 0.0     # P2P / own-account / card-bill payments (excluded from expense)
    transfers_in: float = 0.0      # money received from people (not counted as income)
    refunds_total: float = 0.0     # refunds/reversals netted off spending


# ---------------------------------------------------------------------------
# Core computation
# ---------------------------------------------------------------------------

def _parse_date(d: Optional[str]) -> Optional[date]:
    if not d:
        return None
    try:
        return datetime.strptime(d, "%Y-%m-%d").date()
    except ValueError:
        return None


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    mid = len(s) // 2
    return s[mid] if len(s) % 2 else (s[mid - 1] + s[mid]) / 2


def compute_budget(
    txns: list[CategorisedTransaction],
    income: Optional[float] = None,
    exclude_transfers: bool = True,
) -> BudgetSummary:
    """Compute complete budget summary from categorised transactions.

    Args:
        txns: List of categorised transactions.
        income: Override income figure (INR). If None, sum credits in Salary category.
        exclude_transfers: If True (default), debits categorised "Transfer" (money sent
            to people, own accounts, credit-card bill payments) are reported as
            transfers_out instead of being counted as spending.

    Returns:
        BudgetSummary with all computed fields.
    """
    if not txns:
        return BudgetSummary(
            period_start=None, period_end=None, days_covered=0,
            total_income=0, total_expense=0, net=0, savings_rate=0,
            by_category={},
            needs_total=0, wants_total=0, savings_total=0,
            needs_pct=0, wants_pct=0, savings_pct=0,
            needs_target=0, wants_target=0, savings_target=0,
            needs_delta=0, wants_delta=0, savings_delta=0,
        )

    # Collect dates and amounts
    dates = [_parse_date(t.date) for t in txns if t.date]
    period_start = str(min(dates)) if dates else None
    period_end = str(max(dates)) if dates else None
    if dates:
        days_covered = (max(dates) - min(dates)).days + 1
    else:
        days_covered = 0

    # Totals by category (debits only for spending)
    by_category: dict[str, float] = defaultdict(float)
    total_income_detected = 0.0
    total_expense = 0.0
    transfers_out = transfers_in = refunds_total = 0.0
    n_failed = 0
    n_parsed = 0

    for t in txns:
        if t.parse_method == "failed":
            n_failed += 1
            continue
        n_parsed += 1
        amt = t.amount or 0.0
        if t.transaction_type == "credit":
            if t.category == "Salary":
                total_income_detected += amt
            elif t.category == "Refund":
                # money back from a purchase: reduces spending, is not income
                refunds_total += amt
                by_category["Refund"] = by_category.get("Refund", 0.0) - amt
                total_expense -= amt
            elif t.category == "Transfer":
                transfers_in += amt
        elif t.transaction_type == "debit":
            cat = t.category or "Other"
            if exclude_transfers and cat == "Transfer":
                transfers_out += amt
                continue
            by_category[cat] = by_category.get(cat, 0.0) + amt
            total_expense += amt

    total_income = income if income is not None else total_income_detected

    # 50/30/20 split
    needs_total, wants_total, savings_total = _split_5030_20(by_category)
    net = total_income - total_expense

    # Base for percentages: income if available, else total_expense
    base = total_income if total_income > 0 else total_expense
    if base == 0:
        needs_pct = wants_pct = savings_pct = savings_rate = 0.0
    else:
        needs_pct = round(needs_total / base * 100, 1)
        wants_pct = round(wants_total / base * 100, 1)
        savings_pct = round(savings_total / base * 100, 1)
        savings_rate = round(net / total_income * 100, 1) if total_income > 0 else 0.0

    # 50/30/20 targets from income (or expense if no income)
    needs_target = round(base * 0.50, 2)
    wants_target = round(base * 0.30, 2)
    savings_target = round(base * 0.20, 2)

    needs_delta = round(needs_total - needs_target, 2)
    wants_delta = round(wants_total - wants_target, 2)
    savings_delta = round(savings_total - savings_target, 2)

    return BudgetSummary(
        period_start=period_start,
        period_end=period_end,
        days_covered=days_covered,
        total_income=round(total_income, 2),
        total_expense=round(total_expense, 2),
        net=round(net, 2),
        savings_rate=savings_rate,
        by_category=dict(by_category),
        needs_total=round(needs_total, 2),
        wants_total=round(wants_total, 2),
        savings_total=round(savings_total, 2),
        needs_pct=needs_pct,
        wants_pct=wants_pct,
        savings_pct=savings_pct,
        needs_target=needs_target,
        wants_target=wants_target,
        savings_target=savings_target,
        needs_delta=needs_delta,
        wants_delta=wants_delta,
        savings_delta=savings_delta,
        n_transactions=len(txns),
        n_parsed=n_parsed,
        n_failed=n_failed,
        transfers_out=round(transfers_out, 2),
        transfers_in=round(transfers_in, 2),
        refunds_total=round(refunds_total, 2),
    )


def _split_5030_20(by_category: dict[str, float]) -> tuple[float, float, float]:
    """Split category totals into Needs / Wants / Savings buckets.

    Returns: (needs_total, wants_total, savings_total)
    """
    needs = sum(v for k, v in by_category.items() if k in NEEDS_CATEGORIES)
    savings = sum(v for k, v in by_category.items() if k in SAVINGS_CATEGORIES)
    wants = sum(v for k, v in by_category.items() if k not in NEEDS_CATEGORIES and k not in SAVINGS_CATEGORIES)
    return needs, wants, savings


def detect_recurring(txns: list[CategorisedTransaction]) -> list[RecurringPayment]:
    """Detect recurring payment patterns.

    A payment is recurring if the same merchant appears >= 2 times across
    different calendar months.

    Returns list of RecurringPayment sorted by typical_amount desc.
    """
    # Group by (merchant, category)
    by_merchant: dict[tuple[str, str], list[tuple[str, float]]] = defaultdict(list)
    for t in txns:
        if t.transaction_type != "debit":
            continue
        merchant = (t.merchant or "unknown").strip().lower()
        cat = t.category or "Other"
        month = t.date[:7] if t.date and len(t.date) >= 7 else "unknown"
        amt = t.amount or 0.0
        by_merchant[(merchant, cat)].append((month, amt))

    result = []
    for (merchant, cat), entries in by_merchant.items():
        months = sorted(set(m for m, _ in entries))
        if len(months) >= 2:
            amounts = [a for _, a in entries]
            result.append(RecurringPayment(
                merchant=merchant,
                category=cat,
                typical_amount=round(_median(amounts), 2),
                occurrences=len(entries),
                months=months,
            ))

    return sorted(result, key=lambda r: r.typical_amount, reverse=True)


def compute_pace(
    txns: list[CategorisedTransaction],
    today: Optional[date] = None,
) -> dict:
    """Project month-end spend based on current pace.

    Uses the current month's transactions to project the full month.
    Returns a dict with:
      current_month_spend, days_elapsed, days_in_month,
      projected_month_spend, daily_rate, top_categories_pace
    """
    if today is None:
        today = date.today()
        txn_dates = [_parse_date(t.date) for t in txns if t.date and t.parse_method != "failed"]
        txn_dates = [d for d in txn_dates if d]
        if txn_dates and max(txn_dates).strftime("%Y-%m") != today.strftime("%Y-%m"):
            today = max(txn_dates)   # analyse the latest month in the data
    current_month = today.strftime("%Y-%m")
    days_in_month = _days_in_month(today.year, today.month)
    days_elapsed = today.day

    # Filter to current month debits
    month_txns = [
        t for t in txns
        if t.transaction_type == "debit"
        and t.date
        and t.date.startswith(current_month)
        and t.parse_method != "failed"
        and t.category != "Transfer"
    ]

    total_this_month = sum(t.amount or 0 for t in month_txns)
    daily_rate = total_this_month / days_elapsed if days_elapsed > 0 else 0.0
    projected = round(daily_rate * days_in_month, 2)

    # By category pace
    by_cat: dict[str, float] = defaultdict(float)
    for t in month_txns:
        by_cat[t.category or "Other"] += t.amount or 0

    top_cats = sorted(by_cat.items(), key=lambda x: x[1], reverse=True)[:5]
    top_categories_pace = {
        cat: {
            "spent": round(amt, 2),
            "projected": round(amt / days_elapsed * days_in_month, 2) if days_elapsed else amt,
        }
        for cat, amt in top_cats
    }

    return {
        "current_month": current_month,
        "current_month_spend": round(total_this_month, 2),
        "days_elapsed": days_elapsed,
        "days_in_month": days_in_month,
        "daily_rate": round(daily_rate, 2),
        "projected_month_spend": projected,
        "reference_date": today.isoformat(),
        "top_categories_pace": top_categories_pace,
    }


def _days_in_month(year: int, month: int) -> int:
    """Return number of days in a given month."""
    import calendar
    return calendar.monthrange(year, month)[1]
