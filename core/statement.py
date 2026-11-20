"""core/statement.py – bank statement CSV import.

Converts a bank statement export (Date, Narration, Withdrawal, Deposit, Balance …)
into SBI-style SMS strings so the existing parser → categoriser → budget pipeline
runs unchanged. No new numeric logic: amounts come straight from the file.

Handles the layouts the big banks and finance apps export:
  * separate Debit / Credit columns        (HDFC, SBI, ICICI, Axis, Kotak …, header names vary)
  * one signed Amount column               (-450.00 = debit, 55000 = credit)
  * Amount + a Dr/Cr / Type column, or "450.00 Dr" / "55,000 Cr" suffixes
  * Amount only, with a Balance column     (debit/credit is inferred from the balance change)
  * comma, semicolon, tab or pipe delimited; preamble lines before the header; footer/opening-balance rows

  statement_to_sms(csv_text) -> list[str]   ([] if it is not a statement)
"""

import csv
import io
import re
from datetime import datetime
from typing import Optional

_DATE_FORMATS = (
    "%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%d-%m-%y", "%Y-%m-%d", "%Y/%m/%d", "%d-%b-%Y", "%d-%b-%y",
    "%d %b %Y", "%d %b %y", "%d/%b/%Y", "%d.%m.%Y", "%d.%m.%y", "%d %B %Y", "%B %d, %Y", "%b %d, %Y",
)
_CREDIT_HINT = re.compile(r"\b(salary|sal|credit|refund|interest|received|deposit|dividend|cashback|reversal|neft cr|imps cr)\b", re.I)


def _norm(h: str) -> str:
    """'Withdrawal Amount (INR )' -> 'withdrawal amount'; 'Withdrawal (Dr)' -> 'withdrawal'; 'Chq./Ref.No.' -> 'chq ref no'."""
    h = re.sub(r"\(.*?\)", " ", (h or "").lower())
    h = re.sub(r"[^a-z0-9/ ]+", " ", h)
    return re.sub(r"\s+", " ", h).strip()


def _find_columns(header: list[str]) -> dict:
    """Map logical columns (date/narr/debit/credit/bal/amt/typ) to indices using tolerant header matching."""
    raw = [(h or "").lower() for h in header]
    h = [_norm(x) for x in header]
    ci: dict[str, Optional[int]] = dict(date=None, narr=None, debit=None, credit=None, bal=None, amt=None, typ=None)

    def first(pred, exclude=()):
        for i, name in enumerate(h):
            if i not in exclude and name and pred(name, raw[i]):
                return i
        return None

    # date: prefer a transaction/posting date over a value date
    ci["date"] = (first(lambda n, r: "date" in n and "value" not in n and "valu" not in n)
                  if first(lambda n, r: "date" in n and "value" not in n) is not None
                  else first(lambda n, r: "date" in n or n in ("dt", "tran dt", "txn dt")))
    ci["narr"] = first(lambda n, r: any(k in n for k in ("narration", "description", "particulars", "remarks", "details", "transaction detail")))
    used = {v for v in (ci["date"], ci["narr"]) if v is not None}
    ci["bal"] = first(lambda n, r: "balance" in n or n in ("bal", "closing bal", "running bal"), used)
    used |= {ci["bal"]} if ci["bal"] is not None else set()
    ci["debit"] = first(lambda n, r: any(k in n for k in ("withdraw", "debit", "paid out", "money out", "outflow"))
                        or n in ("dr", "debit amt", "dr amt", "withdrawals"), used)
    used |= {ci["debit"]} if ci["debit"] is not None else set()
    ci["credit"] = first(lambda n, r: any(k in n for k in ("deposit", "credit", "paid in", "money in", "inflow"))
                         or n in ("cr", "credit amt", "cr amt", "deposits"), used)
    used |= {ci["credit"]} if ci["credit"] is not None else set()
    ci["typ"] = first(lambda n, r: n in ("dr/cr", "cr/dr", "type", "txn type", "transaction type", "debit/credit", "credit/debit", "dr cr"), used)
    used |= {ci["typ"]} if ci["typ"] is not None else set()
    ci["amt"] = first(lambda n, r: n in ("amount", "txn amount", "transaction amount", "amt", "amount inr", "value"), used)
    return ci


def _num(s: str) -> Optional[float]:
    """Absolute amount from '1,200.00', '(1,200.00)', '-450', '450.00 Dr', 'Rs. 450'. None if empty/zero."""
    s = re.sub(r"[^\d.]", "", (s or "").replace(",", ""))
    try:
        v = float(s)
    except ValueError:
        return None
    return v if v > 0 else None


def _sign(s: str) -> Optional[str]:
    """'debit' / 'credit' if the cell itself says so (minus sign, brackets, Dr/Cr suffix), else None."""
    t = (s or "").strip()
    if not t:
        return None
    if t.startswith("-") or (t.startswith("(") and t.endswith(")")) or re.search(r"\bd(?:r|ebit)?\.?$", t, re.I):
        return "debit"
    if t.startswith("+") or re.search(r"\bc(?:r|redit)?\.?$", t, re.I):
        return "credit"
    return None


def _date(s: str):
    s = (s or "").strip()
    for f in _DATE_FORMATS:
        try:
            return datetime.strptime(s, f)
        except ValueError:
            continue
    return None


_SKIP_TOKENS = {"payment", "upi", "dr", "cr", "p2m", "p2p", "p2a", "pos", "imps", "neft", "rtgs", "ach", "atm", "ecom", "pur", "txn",
                "okaxis", "okicici", "oksbi", "okhdfcbank", "ybl", "paytm", "upiint"}


def _clean_narration(n: str) -> str:
    """UPI/DR/633000111222/SWIGGY/YESB/swiggy@ybl -> SWIGGY ; NEFT-ACME LTD-SALARY -> ACME LTD SALARY."""
    n = re.sub(r"\s+", " ", (n or "").strip())
    parts = [p.strip() for p in re.split(r"[/\-]", n) if p.strip()]
    if parts and parts[0].upper() in ("NEFT", "IMPS", "ACH", "RTGS") and len(parts) > 1:
        rest = [p for p in parts[1:] if p.upper() not in ("CR", "DR") and not re.fullmatch(r"[A-Z0-9]{10,}", p)]
        return " ".join(rest).upper()[:40] or n.upper()[:40]
    if parts and parts[0].upper() in ("UPI", "POS", "ATM", "ACH"):
        for p in parts[1:]:
            if (p.isdigit() or "@" in p or p.lower() in _SKIP_TOKENS or re.fullmatch(r"[A-Z]{4}0?\w{0,7}", p)
                    and p.upper() in {"YESB", "HDFC", "ICIC", "SBIN", "UTIB", "KKBK", "PUNB", "BARB", "CNRB", "IDIB", "UBIN", "IDFB", "INDB"}):
                continue
            return p.upper()[:40]
    return n.upper()[:40] or "UNKNOWN"


def _detect_delimiter(text: str) -> str:
    sample = "\n".join(text.splitlines()[:40])
    counts = {d: sample.count(d) for d in (",", ";", "\t", "|")}
    best = max(counts, key=counts.get)
    return best if counts[best] else ","


def statement_to_sms(csv_text: str) -> list[str]:
    rows = list(csv.reader(io.StringIO(csv_text), delimiter=_detect_delimiter(csv_text)))
    # Statements often have preamble lines: find the header row.
    hi, ci = None, None
    for i, r in enumerate(rows):
        cols = _find_columns(r)
        if cols["date"] is not None and cols["narr"] is not None and (
                cols["debit"] is not None or cols["credit"] is not None or cols["amt"] is not None):
            hi, ci = i, cols
            break
    if hi is None:
        return []

    def get(r, k):
        return r[ci[k]] if ci[k] is not None and ci[k] < len(r) else ""

    parsed = []
    prev_bal: Optional[float] = None
    for r in rows[hi + 1:]:
        d = _date(get(r, "date"))
        if d is None:
            continue
        bal = _num(get(r, "bal"))
        debit, credit = _num(get(r, "debit")), _num(get(r, "credit"))
        narr_raw = get(r, "narr")
        if debit is None and credit is None and ci["amt"] is not None:
            cell = get(r, "amt")
            a = _num(cell)
            if a is not None:
                kind = _sign(cell)
                if kind is None and ci["typ"] is not None:
                    t = get(r, "typ").strip().lower()
                    kind = "credit" if t.startswith("c") else "debit" if t.startswith("d") else None
                if kind is None and bal is not None and prev_bal is not None:
                    kind = "credit" if bal > prev_bal else "debit" if bal < prev_bal else None
                if kind is None:
                    kind = "credit" if _CREDIT_HINT.search(narr_raw) else "debit"
                debit, credit = (a, None) if kind == "debit" else (None, a)
        if bal is not None:
            prev_bal = bal
        if debit is None and credit is None:
            continue
        parsed.append((d, debit, credit, narr_raw, bal))

    out: list[str] = []
    for d, debit, credit, narr_raw, bal in parsed:
        ds = d.strftime("%d-%b-%y")
        narr = _clean_narration(narr_raw)
        bal_txt = f" Avl Bal: Rs {bal:,.2f}" if bal is not None else ""     # never invent a balance
        if debit is not None:
            out.append(f"Rs {debit:,.2f} debited from A/c XX0000 on {ds} at {narr}.{bal_txt} —SBI")
        else:
            out.append(f"Rs {credit:,.2f} credited to A/c XX0000 on {ds} ({narr}).{bal_txt} —SBI")
    return out
