"""
core/insights.py — Spending insights computed in plain Python (no AI).

These answer the most common asks from users of Indian UPI expense trackers:
  * "Which subscriptions am I paying for, and what do they cost per year?"
  * "Tell me only when something is unusual" (anomalies, not constant alerts)
  * "Dozens of ₹20 chai/auto payments hide the big stuff" (small-spend bucket)
  * "My month starts on salary day, not the 1st" (salary-cycle filter)
  * "Help me at tax time" (80C / 80D tags)
  * "Let me export my data" (CSV rows)

Public API:
  detect_subscriptions(txns) -> list[Subscription]
  detect_anomalies(txns, min_amount=500) -> list[Anomaly]
  small_spend_summary(txns, threshold=100) -> dict
  weekly_spend(txns) -> list[dict]
  filter_salary_cycle(txns, cycle_start_day, reference=None) -> (list, start, end)
  tax_tags(txns) -> dict[str, list]
  transactions_to_rows(txns) -> list[dict]
  rows_to_csv(rows) -> str
"""

from __future__ import annotations

import csv
import io
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Iterable, Optional

from core.categoriser import SUBSCRIPTION_MERCHANTS, CategorisedTransaction


def _d(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


def _spend(txns: Iterable[CategorisedTransaction]) -> list[CategorisedTransaction]:
    """Debits that are real spending (parsed, not transfers)."""
    return [
        t for t in txns
        if t.parse_method != "failed" and t.transaction_type == "debit"
        and t.category != "Transfer" and t.amount
    ]


def _median(xs: list[float]) -> float:
    s = sorted(xs)
    if not s:
        return 0.0
    m = len(s) // 2
    return s[m] if len(s) % 2 else (s[m - 1] + s[m]) / 2


# ---------------------------------------------------------------------------
# Subscriptions
# ---------------------------------------------------------------------------

@dataclass
class Subscription:
    merchant: str
    monthly_amount: float
    annual_cost: float
    last_charged: Optional[str]
    times_seen: int
    source: str          # "known-subscription" | "recurring"


def _sub_key(merchant: str) -> Optional[str]:
    m = merchant.lower()
    for known in sorted(SUBSCRIPTION_MERCHANTS, key=len, reverse=True):
        if re.search(rf"(?<![a-z0-9]){re.escape(known)}(?![a-z0-9])", m):
            return known
    return None


def detect_subscriptions(txns: list[CategorisedTransaction]) -> list[Subscription]:
    """Known subscription merchants (Netflix, Spotify, gym…) plus anything that
    repeats at a similar amount in 2+ different months.

    Sorted by annual cost, highest first.
    """
    groups: dict[str, list[CategorisedTransaction]] = defaultdict(list)
    sources: dict[str, str] = {}
    for t in _spend(txns):
        merchant = (t.merchant or "").strip()
        if not merchant:
            continue
        key = _sub_key(merchant)
        if key:
            groups[key].append(t)
            sources[key] = "known-subscription"
        else:
            groups[merchant.lower()].append(t)
            sources.setdefault(merchant.lower(), "recurring")

    subs = []
    for key, items in groups.items():
        months = {t.date[:7] for t in items if t.date}
        amounts = [t.amount for t in items]
        med = _median(amounts)
        if sources[key] == "recurring":
            # needs 2+ months and a stable amount (within 10% of the median)
            if len(months) < 2 or any(abs(a - med) > 0.10 * med for a in amounts):
                continue
            if items[0].category in ("Rent", "EMI_Loan", "Savings_Investment", "Utilities"):
                continue  # fixed obligations and bills (amount varies) are shown elsewhere
        latest = max((t.date for t in items if t.date), default=None)
        display = items[-1].merchant or key
        subs.append(Subscription(
            merchant=display.title() if display.isupper() else display,
            monthly_amount=round(med, 2),
            annual_cost=round(med * 12, 2),
            last_charged=latest,
            times_seen=len(items),
            source=sources[key],
        ))
    return sorted(subs, key=lambda s: s.annual_cost, reverse=True)


# ---------------------------------------------------------------------------
# Anomalies
# ---------------------------------------------------------------------------

@dataclass
class Anomaly:
    txn_id: str
    date: Optional[str]
    merchant: str
    category: str
    amount: float
    reason: str
    severity: str        # "high" | "medium"


def detect_anomalies(
    txns: list[CategorisedTransaction],
    min_amount: float = 500.0,
) -> list[Anomaly]:
    """Flag unusual debits only — not every transaction.

    Rules (all pure arithmetic):
      * amount >= 3x the median of that category (needs 3+ data points), or
      * amount >= 25% of the period's total spend (one purchase dominates), or
      * debit to an unknown/unrecognised payee >= ₹5,000 (possible fraud check).
    """
    spend = _spend(txns)
    total = sum(t.amount for t in spend) or 1.0
    by_cat: dict[str, list[float]] = defaultdict(list)
    for t in spend:
        by_cat[t.category].append(t.amount)

    out: list[Anomaly] = []
    for t in spend:
        if t.amount < min_amount or t.category in ("Rent", "EMI_Loan", "Savings_Investment"):
            continue
        reasons = []
        severity = "medium"
        amounts = by_cat[t.category]
        if len(amounts) >= 3:
            med = _median(amounts)
            if med > 0 and t.amount >= 3 * med:
                reasons.append(f"{t.amount / med:.1f}x your usual {t.category} spend (median ₹{med:,.0f})")
        if t.amount >= 0.25 * total and len(spend) >= 5:
            reasons.append(f"{t.amount / total * 100:.0f}% of all spending this period")
            severity = "high"
        if t.category == "Other" and t.amount >= 5000:
            reasons.append("large payment to an unrecognised payee — check you made it")
            severity = "high"
        if reasons:
            out.append(Anomaly(
                txn_id=t.id, date=t.date, merchant=t.merchant or "Unknown",
                category=t.category, amount=t.amount,
                reason="; ".join(reasons), severity=severity,
            ))
    out += _large_transfer_alerts(txns)
    return sorted(out, key=lambda a: (a.severity != "high", -a.amount))


LARGE_TRANSFER_MIN = 10_000.0     # a one-off transfer at or above this to a payee seen only once is worth a look
LARGE_TRANSFER_HIGH = 25_000.0


def _large_transfer_alerts(txns: list[CategorisedTransaction]) -> list["Anomaly"]:
    """Money sent to a person / unknown UPI ID is kept out of 'spending', but a big one-off transfer to a payee
    seen only once is exactly what a fraud or mistaken-payment check should surface."""
    sent = [t for t in txns if t.transaction_type == "debit" and t.category == "Transfer"
            and t.amount and t.parse_method != "failed"]
    seen: dict[str, int] = defaultdict(int)
    for t in sent:
        seen[(t.merchant or "").strip().lower()] += 1
    out = []
    for t in sent:
        key = (t.merchant or "").strip().lower()
        if t.amount >= LARGE_TRANSFER_MIN and seen[key] == 1:
            out.append(Anomaly(
                txn_id=t.id, date=t.date, merchant=t.merchant or "Unknown", category="Transfer", amount=t.amount,
                reason="large one-off transfer to a payee you haven't paid before — check you made it",
                severity="high" if t.amount >= LARGE_TRANSFER_HIGH else "medium"))
    return out


# ---------------------------------------------------------------------------
# Small-spend bucket, weekly trend
# ---------------------------------------------------------------------------

def small_spend_summary(txns: list[CategorisedTransaction], threshold: float = 100.0) -> dict:
    """Group tiny payments (chai, auto, snacks) so they don't drown the big ones,
    but still show what they add up to."""
    spend = _spend(txns)
    small = [t for t in spend if t.amount < threshold]
    total = sum(t.amount for t in spend)
    small_total = sum(t.amount for t in small)
    days = {t.date for t in spend if t.date}
    return {
        "threshold": threshold,
        "count": len(small),
        "total": round(small_total, 2),
        "share_pct": round(small_total / total * 100, 1) if total else 0.0,
        "per_day": round(small_total / len(days), 2) if days else 0.0,
        "monthly_estimate": round(small_total / len(days) * 30, 2) if days else 0.0,
    }


def weekly_spend(txns: list[CategorisedTransaction]) -> list[dict]:
    """Spending per ISO week (Mon–Sun) for a compact weekly summary."""
    weeks: dict[date, float] = defaultdict(float)
    for t in _spend(txns):
        d = _d(t.date)
        if d:
            weeks[d - timedelta(days=d.weekday())] += t.amount
    return [
        {"week_start": wk.isoformat(), "spend": round(v, 2)}
        for wk, v in sorted(weeks.items())
    ]


# ---------------------------------------------------------------------------
# Salary-cycle budgeting
# ---------------------------------------------------------------------------

def cycle_bounds(cycle_start_day: int, reference: date) -> tuple[date, date]:
    """Start/end of the pay cycle containing `reference`.

    cycle_start_day=1 is a calendar month; 27 means 27th → 26th of next month.
    Days past month-end clamp (e.g. 31 in February → last day of February).
    """
    import calendar

    def _clamped(y: int, m: int, d: int) -> date:
        return date(y, m, min(d, calendar.monthrange(y, m)[1]))

    if not 1 <= cycle_start_day <= 31:
        raise ValueError("cycle_start_day must be 1–31")
    start = _clamped(reference.year, reference.month, cycle_start_day)
    if reference < start:
        y, m = (reference.year - 1, 12) if reference.month == 1 else (reference.year, reference.month - 1)
        start = _clamped(y, m, cycle_start_day)
    y, m = (start.year + 1, 1) if start.month == 12 else (start.year, start.month + 1)
    end = _clamped(y, m, cycle_start_day) - timedelta(days=1)
    return start, end


def filter_salary_cycle(
    txns: list[CategorisedTransaction],
    cycle_start_day: int,
    reference: Optional[date] = None,
) -> tuple[list[CategorisedTransaction], date, date]:
    """Keep transactions inside the pay cycle that contains `reference`
    (default: the latest transaction date). Undated transactions are dropped."""
    dated = [(t, _d(t.date)) for t in txns]
    if reference is None:
        known = [d for _, d in dated if d]
        reference = max(known) if known else date.today()
    start, end = cycle_bounds(cycle_start_day, reference)
    kept = [t for t, d in dated if d and start <= d <= end]
    return kept, start, end


# ---------------------------------------------------------------------------
# Tax tags (old regime deductions)
# ---------------------------------------------------------------------------

_80C = re.compile(r"\b(lic|ppf|elss|tax\s*saver|sukanya|nsc|epf|vpf|ulip|tuition|tution|school fees|home loan principal)\b", re.I)
_80D = re.compile(r"\b(health|mediclaim|star health|care health|niva bupa|max bupa|hdfc ergo|preventive health)\b", re.I)
_80CCD1B = re.compile(r"\bnps\b", re.I)


def tax_tags(txns: list[CategorisedTransaction]) -> dict[str, list[dict]]:
    """Tag payments that MAY qualify for old-regime deductions.

    These are hints for the user to verify with receipts — e.g. an SIP is only
    80C if it is an ELSS fund, and tuition fees qualify only for children's
    full-time education.
    """
    tags: dict[str, list[dict]] = {"80C": [], "80D": [], "80CCD(1B)": []}
    for t in _spend(txns):
        text = f"{t.merchant or ''} {t.raw_message or ''}"
        row = {"date": t.date, "merchant": t.merchant, "amount": t.amount}
        if _80D.search(text):
            tags["80D"].append(row)
        elif _80CCD1B.search(text):
            tags["80CCD(1B)"].append(row)
        elif _80C.search(text):
            tags["80C"].append(row)
    return tags


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

EXPORT_COLUMNS = ["date", "type", "amount", "merchant", "category", "bank",
                  "upi_id", "parse_method", "category_method", "raw_sms"]


def transactions_to_rows(txns: list[CategorisedTransaction]) -> list[dict]:
    return [
        {
            "date": t.date or "",
            "type": t.transaction_type or "",
            "amount": t.amount if t.amount is not None else "",
            "merchant": t.merchant or "",
            "category": t.category,
            "bank": t.bank or "",
            "upi_id": t.vpa or "",
            "parse_method": t.parse_method,
            "category_method": t.category_method,
            "raw_sms": t.raw_message,
        }
        for t in txns
    ]


def rows_to_csv(rows: list[dict]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=EXPORT_COLUMNS)
    w.writeheader()
    for r in rows:
        w.writerow({k: r.get(k, "") for k in EXPORT_COLUMNS})
    return buf.getvalue()
