"""
core/parser.py — Hybrid SMS parser for Indian bank/UPI messages.

Strategy:
  1. Regex templates for SBI, HDFC, ICICI, Axis, Kotak, UPI/PhonePe/GPay formats.
  2. LLM fallback (ParsedTransactionLLM schema) for messages regex cannot parse.
  3. Log parse_method: "regex" | "llm" | "failed"

Public API:
  parse_message(text, adapter=None) -> ParsedTransaction
  parse_messages(texts, adapter=None) -> list[ParsedTransaction]
  parse_csv(path, adapter=None) -> list[ParsedTransaction]
"""

import re
import csv
import logging
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Output model (pure dataclass — no LLM dependency)
# ---------------------------------------------------------------------------

@dataclass
class ParsedTransaction:
    id: str
    raw_message: str
    amount: Optional[float]
    transaction_type: Optional[str]   # "debit" | "credit"
    merchant: Optional[str]
    vpa: Optional[str]
    date: Optional[str]               # YYYY-MM-DD
    balance: Optional[float]
    bank: Optional[str]
    parse_method: str                 # "regex" | "llm" | "failed"
    confidence: float                 # 0-1


# ---------------------------------------------------------------------------
# Regex helpers
# ---------------------------------------------------------------------------

def _clean_amount(raw: str) -> float:
    """Remove commas, strip whitespace, return float."""
    return float(raw.replace(",", "").strip())


def _normalise_date(raw: str) -> Optional[str]:
    """Convert common Indian bank SMS date formats to YYYY-MM-DD.

    Handles: 14-Nov-26, 14-Nov-2026, 14Nov26, 14 Nov 2026, 14-11-2026, 14/11/26.
    """
    month_map = {
        "jan": "01", "feb": "02", "mar": "03", "apr": "04",
        "may": "05", "jun": "06", "jul": "07", "aug": "08",
        "sep": "09", "oct": "10", "nov": "11", "dec": "12",
    }
    raw = raw.strip()
    m = re.match(r"(\d{1,2})[-\s]?([A-Za-z]{3})[A-Za-z]*[-\s,]*(\d{2,4})$", raw)
    if m:
        day, mon, yr = m.group(1), m.group(2).lower(), m.group(3)
        month = month_map.get(mon)
        if not month:
            return None
    else:
        m = re.match(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})$", raw)
        if not m:
            return None
        day, month, yr = m.group(1), f"{int(m.group(2)):02d}", m.group(3)
        if not 1 <= int(month) <= 12:
            return None
    if not 1 <= int(day) <= 31:
        return None
    year = f"20{yr}" if len(yr) == 2 else yr
    return f"{year}-{month}-{int(day):02d}"


# ---------------------------------------------------------------------------
# Bank-specific regex patterns
# ---------------------------------------------------------------------------

# Amount pattern (handles 1,250.00 or 1250 etc.)
_AMT = r"Rs\s*([\d,]+(?:\.\d{2})?)"
# Date pattern
_DATE = r"(\d{1,2}-[A-Za-z]{3}-\d{2,4})"
# Balance pattern
_BAL = r"(?:Avl\s*Bal(?:ance)?|Bal(?:ance)?)\s*(?:Rs\s*)?([\d,]+(?:\.\d{2})?)"
# Account last 4
_ACC = r"[Aa][/]?[Cc]\s*(?:No\.?\s*)?XX(\d{4})"
# VPA pattern
_VPA = r"([\w.\-]+@[\w]+)"

PATTERNS: list[tuple[str, dict]] = [
    # --- SBI debit ---
    (
        r"Rs\s*([\d,]+(?:\.\d{2})?)\s+debited from A/c\s+XX(\d{4})\s+on\s+(\d{1,2}-[A-Za-z]{3}-\d{2,4})\s+at\s+(.+?)\.\s*Avl Bal:\s*Rs\s*([\d,]+(?:\.\d{2})?)",
        {"bank": "SBI", "transaction_type": "debit",
         "groups": {"amount": 1, "account_last4": 2, "date": 3, "merchant": 4, "balance": 5}}
    ),
    # --- SBI ATM withdrawal ---
    (
        r"ATM WDL\s+" + _AMT + r"\s+from A/c\s+XX(\d{4})\s+on\s+" + _DATE + r"\s+at\s+(.+?)\.\s*Avl Bal:\s*Rs\s*([\d,]+(?:\.\d{2})?)",
        {"bank": "SBI", "transaction_type": "debit", "merchant": "ATM",
         "groups": {"amount": 1, "account_last4": 2, "date": 3, "atm_loc": 4, "balance": 5}}
    ),
    # --- SBI credit ---
    (
        r"Rs\s*([\d,]+(?:\.\d{2})?)\s+credited to\s+(?:your\s+)?A/c\s+XX(\d{4})\s+on\s+(\d{1,2}-[A-Za-z]{3}-\d{2,4})(?:\s+\(([^)]+)\))?(?:\.\s*(?:Avl\s+)?Bal:\s*Rs\s*([\d,]+(?:\.\d{2})?))?",
        {"bank": "SBI", "transaction_type": "credit",
         "groups": {"amount": 1, "account_last4": 2, "date": 3, "merchant": 4, "balance": 5}}
    ),
    # --- HDFC debit ---
    (
        r"(?:Your\s+)?HDFC\s+Bank\s+A/c\s+XX(\d{4})\s+is\s+debited\s+Rs\s*([\d,]+(?:\.\d{2})?)\s+on\s+(\d{1,2}-[A-Za-z]{3}-\d{2,4})[\.\s]*(?:Info|for):\s*(.+?)\.\s*Avl\s+Bal\s*Rs\s*([\d,]+(?:\.\d{2})?)",
        {"bank": "HDFC", "transaction_type": "debit",
         "groups": {"account_last4": 1, "amount": 2, "date": 3, "merchant": 4, "balance": 5}}
    ),
    # --- HDFC credit ---
    (
        r"Rs\s*([\d,]+(?:\.\d{2})?)\s+credited to\s+(?:your\s+)?(?:HDFC Bank\s+)?A/c\s+XX(\d{4})\s+on\s+(\d{1,2}-[A-Za-z]{3}-\d{2,4})\.\s*(?:NEFT|UPI|IMPS)?\s*(?:from\s+)?(.+?)\.\s*—HDFC",
        {"bank": "HDFC", "transaction_type": "credit",
         "groups": {"amount": 1, "account_last4": 2, "date": 3, "merchant": 4}}
    ),
    # --- ICICI debit ---
    (
        r"(?:Your\s+)?ICICI\s+Bank\s+A/c\s+XX(\d{4})\s+is\s+debited\s+Rs\s*([\d,]+(?:\.\d{2})?)\s+on\s+(\d{1,2}-[A-Za-z]{3}-\d{2,4})[\.\s]*(?:Info|for):\s*(.+?)\.\s*Avl\s+Bal:\s*Rs\s*([\d,]+(?:\.\d{2})?)",
        {"bank": "ICICI", "transaction_type": "debit",
         "groups": {"account_last4": 1, "amount": 2, "date": 3, "merchant": 4, "balance": 5}}
    ),
    # --- ICICI credit ---
    (
        r"Rs\s*([\d,]+(?:\.\d{2})?)\s+credited to\s+(?:your\s+)?(?:ICICI Bank\s+)?A/c\s+XX(\d{4})\s+on\s+(\d{1,2}-[A-Za-z]{3}-\d{2,4})\.\s*(?:UPI Ref:\s*\d+\.)?\s*—ICICI",
        {"bank": "ICICI", "transaction_type": "credit",
         "groups": {"amount": 1, "account_last4": 2, "date": 3}}
    ),
    # --- Axis debit ---
    (
        r"Rs\s*([\d,]+(?:\.\d{2})?)\s+debited from\s+(?:your\s+)?(?:Kotak\s+)?A/c\s+XX(\d{4})\s+on\s+(\d{1,2}-[A-Za-z]{3}-\d{2,4})\s+(?:at|for)\s+(.+?)\.\s*(?:Avl\s*)?Bal(?:ance)?:\s*Rs\s*([\d,]+(?:\.\d{2})?)\s*—Axis",
        {"bank": "Axis", "transaction_type": "debit",
         "groups": {"amount": 1, "account_last4": 2, "date": 3, "merchant": 4, "balance": 5}}
    ),
    # --- Kotak debit ---
    (
        r"Rs\s*([\d,]+(?:\.\d{2})?)\s+debited from\s+your\s+Kotak\s+A/c\s+XX(\d{4})\s+on\s+(\d{1,2}-[A-Za-z]{3}-\d{2,4})\s+for\s+(.+?)\.\s*Bal:\s*Rs\s*([\d,]+(?:\.\d{2})?)",
        {"bank": "Kotak", "transaction_type": "debit",
         "groups": {"amount": 1, "account_last4": 2, "date": 3, "merchant": 4, "balance": 5}}
    ),
    # --- PhonePe / GPay / Paytm UPI sent ---
    (
        r"Sent\s+Rs\s*([\d,]+(?:\.\d{2})?)\s+to\s+([\w.\-@]+)\s+via\s+UPI\s+on\s+(\d{1,2}-[A-Za-z]{3}-\d{2,4})(?:\.\s*UPI\s+Ref:\s*\d+)?(?:\.\s*(?:Balance|Bal(?:ance)?):\s*Rs\s*([\d,]+(?:\.\d{2})?))?",
        {"transaction_type": "debit",
         "groups": {"amount": 1, "vpa_or_merchant": 2, "date": 3, "balance": 4}}
    ),
    # --- PhonePe / GPay / Paytm UPI received ---
    (
        r"Received\s+Rs\s*([\d,]+(?:\.\d{2})?)\s+from\s+([\w.\-@\s]+?)\s+via\s+UPI\s+on\s+(\d{1,2}-[A-Za-z]{3}-\d{2,4})(?:\.\s*UPI\s+Ref:\s*\d+)?(?:\.\s*(?:Available\s+)?Bal(?:ance)?:\s*Rs\s*([\d,]+(?:\.\d{2})?))?",
        {"transaction_type": "credit",
         "groups": {"amount": 1, "vpa_or_merchant": 2, "date": 3, "balance": 4}}
    ),
    # --- NEFT transfer ---
    (
        r"Rs\s*([\d,]+(?:\.\d{2})?)\s+transferred to\s+A/c\s+XX(\d{4})\s+on\s+(\d{1,2}-[A-Za-z]{3}-\d{2,4})\s+via\s+NEFT\.\s*Ref:\s*\S+\.\s*—(\w+)",
        {"transaction_type": "debit",
         "groups": {"amount": 1, "account_last4": 2, "date": 3, "bank": 4}}
    ),
]

# Generic fallbacks (tried after the bank-specific templates above).
# "type_word" groups resolve to debit/credit from the verb in the message.
_GAMT = r"(?:Rs\.?|INR|₹)\s*([\d,]+(?:\.\d{1,2})?)"
_GDATE = r"(\d{1,2}[-\s]?[A-Za-z]{3}[A-Za-z]*[-\s,]*\d{2,4}|\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4})"
_GBAL = r"(?:Avl\.?\s*|Available\s*)?Bal(?:ance)?\.?:?\s*(?:is\s*)?" + _GAMT

PATTERNS += [
    # Rs X debited/credited from/to [your] [Bank] A/c XXnnnn on DATE. Info:/for/at MERCHANT. Avl Bal Rs Y
    (
        _GAMT + r"\s+(debited|credited)\s+(?:from|to|in)\s+(?:your\s+)?(?:[A-Za-z]+\s+)?(?:Bank\s+)?A/c\s+(?:No\.?\s*)?[X*]*(\d{3,4})\s+on\s+"
        + _GDATE + r"\.?\s*(?:Info:?|for|at|towards|by|from)\s*(.+?)\.\s*" + _GBAL,
        {"generic": True,
         "groups": {"amount": 1, "type_word": 2, "account_last4": 3, "date": 4, "merchant": 5, "balance": 6}}
    ),
    # [Your] [Bank] A/c XXnnnn is debited/credited [with|for] Rs X on DATE [for|Info:] MERCHANT. Avl Bal Rs Y
    (
        r"(?:Your\s+)?(?:[A-Za-z]+\s+)?(?:Bank\s+)?A/c\s+(?:No\.?\s*)?[X*]*(\d{3,4})\s+is\s+(debited|credited)\s+(?:with\s+|for\s+|by\s+)?"
        + _GAMT + r"\s+on\s+" + _GDATE + r"\.?\s*(?:Info:?|for|at|towards|by|from)\s*(.+?)\.\s*" + _GBAL,
        {"generic": True,
         "groups": {"account_last4": 1, "type_word": 2, "amount": 3, "date": 4, "merchant": 5, "balance": 6}}
    ),
    # SBI-style UPI: A/C XXnnnn debited by Rs X on date 14Nov26 trf to SWIGGY Refno 123
    (
        r"A/c\s+[X*]*(\d{3,4})\s+(debited|credited)\s+by\s+" + _GAMT + r"\s+on\s+(?:date\s+)?" + _GDATE
        + r"\s+(?:trf\s+to|transfer\s+from|to|from)\s+(.+?)\s+Ref",
        {"generic": True,
         "groups": {"account_last4": 1, "type_word": 2, "amount": 3, "date": 4, "merchant": 5}}
    ),
    # Paid Rs X to MERCHANT [via UPI] on DATE
    (
        r"Paid\s+" + _GAMT + r"\s+to\s+([\w.\-@ &]+?)\s+(?:via\s+\w+\s+)?on\s+" + _GDATE,
        {"transaction_type": "debit",
         "groups": {"amount": 1, "vpa_or_merchant": 2, "date": 3}}
    ),
    # Credit-card bill payment acknowledgement
    (
        r"credit\s+card\s+payment\s+of\s+" + _GAMT + r"\s+(?:has\s+been\s+|is\s+)?received\s+on\s+" + _GDATE,
        {"transaction_type": "credit", "merchant": "CC Payment",
         "groups": {"amount": 1, "date": 2}}
    ),
    # Last resort: amount + debited/credited + date, merchant unknown (lower confidence)
    (
        _GAMT + r"\s+(?:has\s+been\s+|is\s+)?(debited|credited).{0,80}?on\s+" + _GDATE,
        {"generic": True, "confidence": 0.6,
         "groups": {"amount": 1, "type_word": 2, "date": 3}}
    ),
]

# Compiled patterns
_COMPILED_PATTERNS = [(re.compile(pat, re.IGNORECASE), meta) for pat, meta in PATTERNS]


def _detect_bank_from_sender(text: str) -> Optional[str]:
    """Infer bank from common sender markers in the SMS text."""
    t = text.lower()
    if "—sbi" in t or "—sbi" in t or "sbi" in t[-20:]:
        return "SBI"
    if "—hdfc" in t or "hdfc bank" in t:
        return "HDFC"
    if "—icici" in t or "icici bank" in t:
        return "ICICI"
    if "—axis" in t:
        return "Axis"
    if "—kotak" in t or "kotak a/c" in t:
        return "Kotak"
    if "phonePe" in text or "—phonePe" in t:
        return "PhonePe"
    if "gpay" in t or "google pay" in t:
        return "GPay"
    if "paytm" in t:
        return "Paytm"
    return None


def _is_vpa(value: str) -> bool:
    return bool(re.match(r"[\w.\-]+@[\w]+", value.strip()))


_COUNTER = 0


def _next_id() -> str:
    global _COUNTER
    _COUNTER += 1
    return f"TXN{_COUNTER:06d}"


def _try_regex(text: str, txn_id: str) -> Optional[ParsedTransaction]:
    """Attempt all regex patterns; return ParsedTransaction on first match."""
    for pattern, meta in _COMPILED_PATTERNS:
        m = pattern.search(text)
        if not m:
            continue

        groups = meta.get("groups", {})
        amount = None
        transaction_type = meta.get("transaction_type")
        merchant = meta.get("merchant")
        vpa = None
        txn_date = None
        balance = None
        bank = meta.get("bank")
        account_last4 = None

        # Extract named group indices
        for field_name, grp_idx in groups.items():
            try:
                raw = m.group(grp_idx)
            except IndexError:
                raw = None
            if raw is None:
                continue
            raw = raw.strip()

            if field_name == "amount":
                try:
                    amount = _clean_amount(raw)
                except ValueError:
                    pass
            elif field_name == "balance":
                try:
                    balance = _clean_amount(raw)
                except ValueError:
                    pass
            elif field_name == "date":
                txn_date = _normalise_date(raw)
            elif field_name == "merchant":
                # Strip trailing punctuation / bank suffixes
                merchant = re.sub(r"\s*—\w+\s*$", "", raw).strip()
                merchant = re.sub(r"\s*\.\s*$", "", merchant).strip() or None
            elif field_name == "vpa_or_merchant":
                if _is_vpa(raw):
                    vpa = raw
                    merchant = raw.split("@")[0]
                else:
                    merchant = raw
            elif field_name == "account_last4":
                account_last4 = raw
            elif field_name == "bank":
                bank = raw.upper()
            elif field_name == "type_word":
                transaction_type = "debit" if raw.lower().startswith("debit") else "credit"
            elif field_name == "atm_loc":
                merchant = "ATM"  # already set by meta but keep override

        if bank is None:
            bank = _detect_bank_from_sender(text)

        return ParsedTransaction(
            id=txn_id,
            raw_message=text,
            amount=amount,
            transaction_type=transaction_type,
            merchant=merchant,
            vpa=vpa,
            date=txn_date,
            balance=balance,
            bank=bank,
            parse_method="regex",
            confidence=meta.get("confidence", 0.85 if meta.get("generic") else 0.9),
        )

    return None


def _try_llm(text: str, txn_id: str, adapter) -> ParsedTransaction:
    """LLM fallback for messages regex cannot parse."""
    from llm.prompts import SMS_PARSE_PROMPT_V1
    from llm.schemas import ParsedTransactionLLM

    try:
        prompt = SMS_PARSE_PROMPT_V1.format(message=text)
        result: ParsedTransactionLLM = adapter.generate(
            prompt=prompt,
            response_schema=ParsedTransactionLLM,
            temperature=0.1,
        )
        if not result.parseable:
            return _failed(text, txn_id)
        return ParsedTransaction(
            id=txn_id,
            raw_message=text,
            amount=result.amount,
            transaction_type=result.transaction_type,
            merchant=result.merchant,
            vpa=result.vpa,
            date=result.date,
            balance=result.balance,
            bank=result.bank,
            parse_method="llm",
            confidence=result.confidence,
        )
    except Exception as exc:
        logger.warning("LLM parse failed for id=%s: %s", txn_id, exc)
        return _failed(text, txn_id)


def _failed(text: str, txn_id: str) -> ParsedTransaction:
    return ParsedTransaction(
        id=txn_id,
        raw_message=text,
        amount=None,
        transaction_type=None,
        merchant=None,
        vpa=None,
        date=None,
        balance=None,
        bank=None,
        parse_method="failed",
        confidence=0.0,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_message(text: str, adapter=None, txn_id: Optional[str] = None) -> ParsedTransaction:
    """Parse a single bank/UPI SMS message.

    Args:
        text: Raw SMS text.
        adapter: LLM adapter instance for fallback. None = regex-only.
        txn_id: Optional ID; auto-generated if not provided.

    Returns:
        ParsedTransaction with parse_method set to "regex", "llm", or "failed".
    """
    tid = txn_id or _next_id()
    result = _try_regex(text, tid)
    if result is not None:
        return result
    if adapter is not None:
        return _try_llm(text, tid, adapter)
    return _failed(text, tid)


def parse_messages(texts: list[str], adapter=None) -> list[ParsedTransaction]:
    """Parse a list of SMS messages."""
    return [parse_message(t, adapter=adapter) for t in texts]


def parse_csv(path: str | Path, adapter=None) -> list[ParsedTransaction]:
    """Parse messages from a CSV file with a 'raw_sms' column.

    Also reads 'id' column if present for stable IDs.
    """
    path = Path(path)
    results = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            text = row.get("raw_sms", "").strip()
            if not text:
                continue
            tid = row.get("id") or _next_id()
            results.append(parse_message(text, adapter=adapter, txn_id=tid))
    return results
