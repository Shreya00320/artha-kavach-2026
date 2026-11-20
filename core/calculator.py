"""core/calculator.py — answer "how much will X grow / what is the EMI / how much SIP do I need" in chat.

The figures come from core.goals (plain Python, unit-tested) — never from an AI. The parser only pulls the amount,
rate and duration out of the sentence; if any of the three is missing it returns None and the chat falls back to a
normal knowledge answer instead of guessing.

  answer_calculation(message) -> str | None
"""

from __future__ import annotations

import re
from typing import Optional

from core.goals import emi, loan_summary, lump_sum_future_value, sip_future_value, sip_required

_UNITS = {"k": 1e3, "thousand": 1e3, "l": 1e5, "lac": 1e5, "lacs": 1e5, "lakh": 1e5, "lakhs": 1e5,
          "cr": 1e7, "crore": 1e7, "crores": 1e7}
_RATE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:%|percent|per\s?cent|pc\b)", re.I)
_DUR = re.compile(r"(\d+(?:\.\d+)?)\s*(years?|yrs?|y\b|months?|mos?\b)", re.I)
_MONEY = re.compile(r"(?:₹|rs\.?|inr)?\s*(\d[\d,]*(?:\.\d+)?)\s*(k\b|thousand|lakhs?|lacs?|l\b|crores?|cr\b)?", re.I)
_MONTHLY = re.compile(r"\b(?:per\s+month|a\s+month|every\s+month|each\s+month|monthly|/\s*month|/\s*m\b|pm\b|p\.m\.|sip)\b", re.I)
_GOAL_CUE = re.compile(r"\b(reach|goal|target|corpus|need|want|build|get\s+to|how\s+much\s+(?:sip|do\s+i\s+(?:need\s+to\s+)?(?:invest|save)))\b", re.I)


def fmt_inr(x: float) -> str:
    """₹ with Indian digit grouping (₹11,61,695)."""
    n = f"{abs(round(x)):d}"
    if len(n) > 3:
        head, tail = n[:-3], n[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        n = ",".join(parts) + "," + tail
    return ("-" if x < 0 else "") + "₹" + n


def _first_amount(text: str) -> Optional[float]:
    for m in _MONEY.finditer(text):
        raw = m.group(1).replace(",", "")
        try:
            v = float(raw)
        except ValueError:
            continue
        unit = (m.group(2) or "").lower()
        v *= _UNITS.get(unit, 1.0)
        if v > 0:
            return v
    return None


def _extract(message: str):
    """(amount, annual rate %, months) — any of them may be None."""
    t = message.replace(",", "")
    rate_m = _RATE.search(t)
    dur_m = _DUR.search(t)
    rate = float(rate_m.group(1)) if rate_m else None
    months = None
    if dur_m:
        n = float(dur_m.group(1))
        months = int(round(n * 12)) if dur_m.group(2).lower().startswith(("y",)) else int(round(n))
    rest = t
    for m in sorted([x for x in (rate_m, dur_m) if x], key=lambda x: x.start(), reverse=True):
        rest = rest[:m.start()] + " " + rest[m.end():]
    return _first_amount(rest), rate, months


def answer_calculation(message: str) -> Optional[str]:
    t = (message or "").strip()
    if not t or len(t) > 300:
        return None
    low = t.lower()
    amount, rate, months = _extract(t)
    if amount is None or rate is None or months is None:
        return None
    if not (0 <= rate <= 60 and 1 <= months <= 600 and amount <= 1e10):
        return None

    years_txt = f"{months // 12} years" if months % 12 == 0 else f"{months} months"
    is_loan = bool(re.search(r"\b(emi|loan|borrow|borrowed|mortgage)\b", low)) and "sip" not in low

    if is_loan:
        s = loan_summary(amount, rate, months)
        return (f"An EMI on a {fmt_inr(amount)} loan at {rate:g}% a year over {years_txt} is about "
                f"**{fmt_inr(s['emi'])} a month**. You would repay {fmt_inr(s['total_payment'])} in total, of which "
                f"{fmt_inr(s['total_interest'])} is interest ({s['interest_share_pct']:g}% of everything you pay). "
                "Reducing-balance method; check your lender's exact rate, fees and rounding. A shorter tenure or a "
                "part-prepayment cuts the interest a lot.")

    invest_cue = re.search(r"\b(sip|invest|investing|invested|save|saving|deposit|rd|grow|worth|become|fv)\b", low)
    if not invest_cue:
        return None

    if _GOAL_CUE.search(low) and re.search(r"\b(sip|month|monthly|invest|save)\b", low):
        need = sip_required(amount, rate, months)
        put_in = need * months
        return (f"To reach {fmt_inr(amount)} in {years_txt} at an assumed {rate:g}% a year you would need about "
                f"**{fmt_inr(need)} a month**. You would put in around {fmt_inr(put_in)} yourself and growth would "
                f"add the remaining {fmt_inr(max(amount - put_in, 0))}. That growth is an assumption, not a promise — "
                "returns vary every year and can be negative.")

    if _MONTHLY.search(low):
        fv = sip_future_value(amount, rate, months)
        put_in = amount * months
        return (f"Investing {fmt_inr(amount)} a month for {years_txt} at an assumed {rate:g}% a year would grow to "
                f"about **{fmt_inr(fv)}**. You would put in {fmt_inr(put_in)} and growth would add roughly "
                f"{fmt_inr(max(fv - put_in, 0))}. This is an illustration (monthly compounding, money invested at the "
                "start of each month) — real returns are not guaranteed and can be negative in some years. "
                "Fees and taxes are not included.")

    fv = lump_sum_future_value(amount, rate, months)
    return (f"{fmt_inr(amount)} invested once for {years_txt} at an assumed {rate:g}% a year would grow to about "
            f"**{fmt_inr(fv)}** (monthly compounding). That is an illustration, not a promise: returns vary and can "
            "be negative, and fees and taxes are not included.")
