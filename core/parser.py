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
    iso = re.match(r"(\d{4})-(\d{2})-(\d{2})$", raw)
    if iso and 1 <= int(iso.group(2)) <= 12 and 1 <= int(iso.group(3)) <= 31:
        return raw
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


_CHANNEL_PREFIX = re.compile(r"^(?:(?:NACH|ECS|ACH|SI|UPI|POS|IMPS|NEFT|RTGS|ATM)\s*[/\-]\s*|(?:RTGS|NEFT|IMPS)\s+to\s+|(?:to|at|from)\s+)", re.I)


def _tidy_merchant(m: Optional[str]) -> Optional[str]:
    """'NACH/NETFLIX' -> 'NETFLIX'; 'RTGS to LANDLORD PROPERTIES' -> 'LANDLORD PROPERTIES'."""
    if not m:
        return m
    prev = None
    while prev != m:
        prev = m
        m = _CHANNEL_PREFIX.sub("", m).strip()
    return m or None


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
                merchant = _tidy_merchant(merchant)
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
# Field-based fallback parser
#
# The per-bank templates above only match exact shapes. Real SMS vary by bank, product and year, so this
# fallback finds each field independently: amount, debit/credit verb, date, balance, VPA, merchant, bank.
# It also REJECTS messages that are not completed transactions (OTPs, "will be debited" reminders,
# failed/declined payments, balance enquiries, collect requests, promotions, personal chat).
# ---------------------------------------------------------------------------

_CUR_AMT = re.compile(r"(?:Rs\.?|INR|₹)\s*([\d,]*\d(?:\.\d+)?)", re.I)
_BY_AMT = re.compile(r"\b(?:debited|credited)\s+by\s+([\d,]*\d(?:\.\d+)?)", re.I)
_BAL_BEFORE = re.compile(r"(?:avl\.?|available|closing|ledger|total)?\s*(bal(?:ance)?|lmt|limit|cr limit)\W{0,6}(?:is\W{0,3})?$", re.I)
_DUE_BEFORE = re.compile(r"\b(?:min(?:imum)?(?:\s+amt\.?|\s+amount)?\s+due|total\s+(?:amt\.?\s+)?due|amount\s+due|due)\W{0,6}$", re.I)

# Words naming the *product*, not the movement of money: mask before looking for debit/credit verbs
_PRODUCT_MASK = re.compile(r"\b(?:credit|debit)\s+cards?\b|\bcr(?:edit)?\s+limit\b|\bcredit\s+(?:score|line)\b|\bavl\s+cr\b", re.I)

_DEBIT_STRONG = re.compile(r"\b(?:debited|spent|paid|withdrawn|sent|deducted|purchased|transferred)\b|\bpurchase\s+of\b|\bDr\.", re.I)
_CHEQUE = re.compile(r"\bche?que\b|\bchq\b", re.I)
_CREDIT_STRONG = re.compile(r"\b(?:credited|received|deposited|refunded)\b|\bCr\.", re.I)

_FUTURE = re.compile(r"\bwill\s+be\b|\bto\s+be\s+(?:auto-?\s*)?debited\b|\bis\s+due\b|\bdue\s+(?:on|by|date)\b|\bmin(?:imum)?\s+(?:amt\.?\s+|amount\s+)?due\b|\bupcoming\b|\breminder\b|\bscheduled\b", re.I)
_FAILED = re.compile(r"\b(?:failed|declined|unsuccessful|insufficient|not\s+debited|not\s+successful|could\s+not\s+be)\b", re.I)
_PROMO = re.compile(r"\b(?:offer|cashback|hurry|limited\s+period|t&c|tnc|congratulations|eligible|apply\s+now|click|win|free)\b|https?://|bit\.ly", re.I)
_ACCT = re.compile(r"\b(?:a/c|acct?|account|card|ac)\b(?:\s+(?:no|num|number)\.?)?\W{0,4}[A-Za-z ]{0,12}?[X*x]*\d{3,}", re.I)
# A real bank/UPI alert always names a masked account/card, a UPI/transfer channel, or a payment app
_CONTEXT = re.compile(
    r"\b(?:a/c|acct?|account|card|ac)\b(?:\s+(?:no|num|number)\.?)?\W{0,4}[A-Za-z ]{0,12}?[X*x]*\d{3,}|\bupi\b|\bneft\b|\bimps\b|\brtgs\b|\bvpa\b|@\w+|"
    r"\bref(?:erence)?\.?\s*(?:no\.?|id)?\W{0,3}\d{5,}|\brefno\b|\bpaytm\b|\bphonepe\b|\bgpay\b|\bgoogle\s+pay\b|\bwallet\b", re.I)

_DATE_FIND = re.compile(
    r"\b(\d{4}-\d{2}-\d{2})\b|\b(\d{4}):(\d{2}):(\d{2})\b|\b(\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4})\b|\b(\d{1,2}[-\s]?[A-Za-z]{3}[A-Za-z]*[-\s,]*\d{2,4})\b")

_BANKS = [
    (r"\bSBI\b|State\s+Bank", "SBI"), (r"\bHDFC\b", "HDFC"), (r"\bICICI\b", "ICICI"), (r"\bAxis\b", "Axis"),
    (r"\bKotak\b", "Kotak"), (r"\bPNB\b|Punjab\s+National", "PNB"), (r"\bBOB\b|Bank\s+of\s+Baroda", "BoB"),
    (r"\bCanara\b", "Canara"), (r"Union\s+Bank", "Union Bank"), (r"\bIDFC\b", "IDFC FIRST"),
    (r"\bYes\s+Bank\b", "Yes Bank"), (r"\bIndusInd\b", "IndusInd"), (r"\bPaytm\b", "Paytm"),
    (r"\bPhonePe\b", "PhonePe"), (r"\bG\s?Pay\b|Google\s+Pay", "GPay"),
]

_NOISE_MERCHANT = re.compile(r"^(?:your|a/c|ac|acct|account|card|bank|upi|vpa|the|you|rs|inr|neft|imps|rtgs|ref|date|info)\b", re.I)
_NAME = r"[A-Za-z][A-Za-z0-9 &.'\-]{1,30}?"
_END = r"(?=\s+(?:on|via|using|Ref|Refno|UPI|Avl|Bal|Not|If|SMS|Call|Dt|credited|debited|for|from|towards|-)\b|[.;,(/]|\s*$)"
_MERCHANT_PATTERNS = [
    re.compile(r"\bEMI\b", re.I),                                           # handled specially
    re.compile(r"\b(?:trf|transfer(?:red)?)\s+(?:to|from)\s+(?P<m>" + _NAME + r")" + _END, re.I),
    re.compile(r"UPI[/-](?:P2[MA][/-])?(?:\d{6,}[/-])?(?P<m>[A-Za-z]" + _NAME[len("[A-Za-z]"):] + r")" + _END),
    re.compile(r";\s*(?P<m>[A-Z][A-Za-z0-9 &']{1,25}?)\s+(?:credited|debited)\b"),
    re.compile(r"\b(?:NACH|ECS|ACH|AUTOPAY|SI)[/-]\s*(?P<m>[A-Za-z][A-Za-z0-9 &.']{1,25})"),
    re.compile(r"\b(?:NEFT|IMPS|RTGS)[-*/ ]+(?P<m>[A-Za-z][^.;]{2,40}?)(?=\.|;|\s+Avl\b|\s+Ref\b|\s*$)", re.I),
    re.compile(r"\b(?:by|via)\s+(?:NEFT|IMPS|RTGS)\s+from\s+(?P<m>" + _NAME + r")" + _END, re.I),
    re.compile(r"\bto\s+(?P<m>" + _NAME + r")\s+(?:via|using)\b", re.I),
    re.compile(r"\b(?:paid|sent|spent|debited|purchase\w*)\b[^.;]*?\b(?:to|at)\s+(?P<m>" + _NAME + r")" + _END, re.I),
    re.compile(r"\b(?:Received|credited)\b[^.;]*?\bfrom\s+(?P<m>" + _NAME + r")" + _END, re.I),
    re.compile(r"\bfor\s+(?:your\s+)?(?P<m>" + _NAME + r")(?=\s+(?:subscription|order|purchase|payment|on|via)\b|[.;,]|\s*$)", re.I),
    re.compile(r"\b(?:at|to)\s+(?P<m>" + _NAME + r")" + _END, re.I),
]


def _first_valid_date(text: str) -> Optional[str]:
    for m in _DATE_FIND.finditer(text):
        groups = [g for g in m.groups() if g]
        raw = "-".join(groups) if len(groups) == 3 else groups[0]      # yyyy:mm:dd arrives as three groups
        iso = _normalise_date(raw)
        if iso:
            return iso
    return None


def _field_amounts(text: str) -> tuple[Optional[float], Optional[float]]:
    """(transaction amount, balance). Skips balance / limit / due figures when choosing the amount."""
    amount = balance = None
    for m in _CUR_AMT.finditer(text):
        before = text[max(0, m.start() - 28):m.start()]
        try:
            val = _clean_amount(m.group(1))
        except ValueError:
            continue
        if _DUE_BEFORE.search(before):
            continue
        bal = _BAL_BEFORE.search(before)
        if bal:
            if "bal" in bal.group(1).lower() and balance is None:
                balance = val
            continue
        if amount is None:
            amount = val
    if amount is None:
        m = _BY_AMT.search(text)
        if m:
            try:
                amount = _clean_amount(m.group(1))
            except ValueError:
                pass
    return amount, balance


def _field_merchant(text: str, vpa: Optional[str], txn_type: str) -> Optional[str]:
    if vpa:
        return vpa.split("@")[0]
    if re.search(r"\bEMI\b", text, re.I):
        return "EMI"
    for pat in _MERCHANT_PATTERNS[1:]:
        for m in pat.finditer(text):
            cand = re.sub(r"^(?:from|to|at)\s+", "", re.sub(r"\s+", " ", m.group("m")), flags=re.I).strip(" .-;,")
            cand = re.sub(r"\s+(?:Ref|Refno|UPI|Avl|Bal|SMS|Call|Not|If)\b.*$", "", cand, flags=re.I).strip()
            if 2 <= len(cand) <= 40 and not _NOISE_MERCHANT.match(cand) and not re.fullmatch(r"[\d\s]+", cand):
                return cand
    if txn_type == "credit" and re.search(r"\bsalary\b", text, re.I):
        return "Salary"
    return None


def _try_fields(text: str, txn_id: str) -> Optional[ParsedTransaction]:
    """Generic, template-free parse. Returns None for anything that is not a completed transaction."""
    if not text or len(text) > 600:
        return None
    masked = _PRODUCT_MASK.sub(" ", text)
    deb, cre = _DEBIT_STRONG.search(masked), _CREDIT_STRONG.search(masked)
    if not (deb or cre):
        return None                                   # OTPs, balance enquiries, collect requests, chat, offers…
    if _FUTURE.search(text) or _FAILED.search(text):
        return None
    if _CHEQUE.search(text) and not re.search(r"\b(?:debited|credited)\b", text, re.I):
        return None                                   # "cheque received for clearing" is not a completed movement
    if not _CONTEXT.search(text):
        return None                                   # no account / card / UPI context → not a bank alert
    if _PROMO.search(text) and not _ACCT.search(text):
        return None
    amount, balance = _field_amounts(text)
    if amount is None or amount <= 0:
        return None

    # the movement verb that appears first decides debit vs credit
    if deb and cre:
        txn_type = "debit" if deb.start() < cre.start() else "credit"
    else:
        txn_type = "debit" if deb else "credit"

    vm = re.search(r"([A-Za-z0-9][\w.\-]{1,}@[A-Za-z]{2,})", text)
    vpa = vm.group(1) if vm else None
    if vpa:
        vpa = re.sub(r"^(?:UPI|IMPS|NEFT)[-/](?:[A-Za-z0-9]+[-/])*", "", vpa, flags=re.I) or vpa
    bank = None
    for pat, name in _BANKS:
        if re.search(pat, text, re.I):
            bank = name
            break
    return ParsedTransaction(
        id=txn_id, raw_message=text, amount=amount, transaction_type=txn_type,
        merchant=_field_merchant(text, vpa, txn_type), vpa=vpa, date=_first_valid_date(text),
        balance=balance, bank=bank, parse_method="regex", confidence=0.7,
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
    result = _try_fields(text, tid)
    if result is not None:
        return result
    if adapter is not None:
        return _try_llm(text, tid, adapter)
    return _failed(text, tid)


def dedupe_messages(texts: list[str]) -> tuple[list[str], int]:
    """Drop repeated copies of the same SMS (overlapping pastes / exports). Returns (unique, n_removed).

    Only messages that carry a reference number (6+ digits) or a balance figure are de-duplicated: those are
    effectively unique per transaction. Short alerts without either (two identical Rs 20 chai payments the
    same day) are kept, because they can be genuinely separate transactions.
    """
    seen: set[str] = set()
    out: list[str] = []
    removed = 0
    for t in texts:
        key = re.sub(r"\s+", " ", t).strip().lower()
        identifiable = bool(re.search(r"\d{6,}", key) or re.search(r"\b(?:avl\.?\s*)?bal(?:ance)?\b|avlbal", key))
        if identifiable and key in seen:
            removed += 1
            continue
        seen.add(key)
        out.append(t)
    return out, removed


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
