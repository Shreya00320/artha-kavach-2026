"""core/statement.py – bank statement CSV import.

Converts a bank statement export (Date, Narration, Withdrawal, Deposit, Balance …)
into SBI-style SMS strings so the existing parser → categoriser → budget pipeline
runs unchanged. No new numeric logic: amounts come straight from the file.

  statement_to_sms(csv_text) -> list[str]   ([] if it is not a statement)
"""

import csv
import io
import re
from datetime import datetime

_DATE_COLS = ("date", "txn date", "transaction date", "value date", "posting date")
_NARR_COLS = ("narration", "description", "particulars", "transaction remarks", "remarks", "details")
_DEBIT_COLS = ("withdrawal", "withdrawal amt.", "withdrawal amount", "debit", "debit amount", "dr")
_CREDIT_COLS = ("deposit", "deposit amt.", "deposit amount", "credit", "credit amount", "cr")
_BAL_COLS = ("balance", "closing balance", "running balance")
_AMT_COLS = ("amount",)
_TYPE_COLS = ("dr/cr", "type", "cr/dr")

_DATE_FORMATS = ("%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%d-%m-%y", "%Y-%m-%d", "%d-%b-%Y", "%d-%b-%y", "%d %b %Y")


def _col(header: list[str], names: tuple[str, ...]):
    for n in names:
        if n in header:
            return header.index(n)
    return None


def _num(s: str):
    s = re.sub(r"[^\d.]", "", (s or "").replace(",", ""))
    try:
        v = float(s)
    except ValueError:
        return None
    return v if v > 0 else None


def _date(s: str):
    s = (s or "").strip()
    for f in _DATE_FORMATS:
        try:
            return datetime.strptime(s, f)
        except ValueError:
            continue
    return None


def _clean_narration(n: str) -> str:
    """UPI/123456/SWIGGY/okaxis/Payment -> SWIGGY ; keeps the readable merchant part."""
    n = re.sub(r"\s+", " ", (n or "").strip())
    parts = [p for p in re.split(r"[/\-]", n) if p.strip()]
    if parts and parts[0].upper() in ("UPI", "POS", "NEFT", "IMPS", "ACH", "ATM"):
        for p in parts[1:]:
            p = p.strip()
            if p and not p.isdigit() and "@" not in p and p.lower() not in ("payment", "upi", "okaxis", "okicici", "oksbi", "ybl"):
                return p.upper()
    return n.upper()[:40] or "UNKNOWN"


def statement_to_sms(csv_text: str) -> list[str]:
    rows = list(csv.reader(io.StringIO(csv_text)))
    # Statements often have preamble lines: find the header row.
    hi = next((i for i, r in enumerate(rows)
               if _col([c.strip().lower() for c in r], _DATE_COLS) is not None
               and _col([c.strip().lower() for c in r], _NARR_COLS) is not None), None)
    if hi is None:
        return []
    header = [c.strip().lower() for c in rows[hi]]
    ci = {k: _col(header, v) for k, v in dict(date=_DATE_COLS, narr=_NARR_COLS, debit=_DEBIT_COLS,
                                              credit=_CREDIT_COLS, bal=_BAL_COLS, amt=_AMT_COLS,
                                              typ=_TYPE_COLS).items()}
    if ci["debit"] is None and ci["credit"] is None and ci["amt"] is None:
        return []

    out: list[str] = []
    for r in rows[hi + 1:]:
        get = lambda k: (r[ci[k]] if ci[k] is not None and ci[k] < len(r) else "")
        d = _date(get("date"))
        if d is None:
            continue
        debit, credit = _num(get("debit")), _num(get("credit"))
        if debit is None and credit is None and ci["amt"] is not None:
            a = _num(get("amt"))
            is_cr = get("typ").strip().lower().startswith("c")
            debit, credit = (None, a) if is_cr else (a, None)
        if debit is None and credit is None:
            continue
        ds = d.strftime("%d-%b-%y")
        narr = _clean_narration(get("narr"))
        bal = _num(get("bal"))
        bal_txt = f" Avl Bal: Rs {bal:,.2f}" if bal is not None else " Avl Bal: Rs 0.00"
        if debit is not None:
            out.append(f"Rs {debit:,.2f} debited from A/c XX0000 on {ds} at {narr}.{bal_txt} —SBI")
        else:
            out.append(f"Rs {credit:,.2f} credited to A/c XX0000 on {ds} ({narr}).{bal_txt} —SBI")
    return out
