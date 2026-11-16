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
    """Convert dd-Mon-yy or dd-Mon-yyyy to YYYY-MM-DD."""
    month_map = {
        "jan": "01", "feb": "02", "mar": "03", "apr": "04",
        "may": "05", "jun": "06", "jul": "07", "aug": "08",
        "sep": "09", "oct": "10", "nov": "11", "dec": "12",
    }
    m = re.match(r"(\d{1,2})-([A-Za-z]{3})-(\d{2,4})", raw.strip())
    if not m:
        return None
    day, mon, yr = m.group(1), m.group(2).lower(), m.group(3)
    month = month_map.get(mon)
    if not month:
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
            confidence=0.9,
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
