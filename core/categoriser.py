"""
core/categoriser.py — Transaction categoriser.

Strategy:
  1. Merchant lookup table (~50+ merchants) → category, confidence=1.0
  2. LLM fallback (MerchantCategoryLLM schema) for unknown merchants
  3. Final fallback: "Other"
  4. In-memory cache: keyed by lowercase merchant name

Public API:
  categorise(txn, adapter=None) -> CategorisedTransaction
  categorise_transactions(txns, adapter=None) -> list[CategorisedTransaction]
"""

import logging
from dataclasses import dataclass
from typing import Optional

from core.parser import ParsedTransaction

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Category taxonomy (must match SPEC and schemas.py)
# ---------------------------------------------------------------------------

VALID_CATEGORIES = {
    "Food", "Transport", "Shopping", "Entertainment", "Utilities",
    "Healthcare", "Education", "Rent", "EMI_Loan", "Savings_Investment",
    "Salary", "Transfer", "ATM", "Other",
}

# ---------------------------------------------------------------------------
# Merchant lookup table
# ---------------------------------------------------------------------------

MERCHANT_LOOKUP: dict[str, str] = {
    # Food & Delivery
    "swiggy": "Food",
    "zomato": "Food",
    "dominos": "Food",
    "domino's": "Food",
    "mcdonalds": "Food",
    "mcdonald's": "Food",
    "kfc": "Food",
    "pizza hut": "Food",
    "blinkit": "Food",
    "zepto": "Food",
    "bigbasket": "Food",
    "grofers": "Food",
    "dunzo": "Food",
    "box8": "Food",
    "faasos": "Food",
    "chai point": "Food",
    "cafe coffee day": "Food",
    "starbucks": "Food",
    "haldirams": "Food",
    "d-mart": "Shopping",
    "dmart": "Shopping",
    "big bazaar": "Shopping",
    # Transport
    "uber": "Transport",
    "ola": "Transport",
    "rapido": "Transport",
    "metro card recharge": "Transport",
    "metro": "Transport",
    "irctc": "Transport",
    "makemytrip": "Transport",
    "goibibo": "Transport",
    "redbus": "Transport",
    "petrol pump": "Transport",
    "fuel": "Transport",
    "autorickshaw": "Transport",
    # Shopping
    "amazon": "Shopping",
    "flipkart": "Shopping",
    "myntra": "Shopping",
    "meesho": "Shopping",
    "nykaa": "Shopping",
    "ajio": "Shopping",
    "decathlon": "Shopping",
    "crossword": "Shopping",
    "fabindia": "Shopping",
    "reliance smart": "Shopping",
    "vijay sales": "Shopping",
    "croma": "Shopping",
    "tata cliq": "Shopping",
    "lenskart": "Shopping",
    "bewakoof": "Shopping",
    "pepperfry": "Shopping",
    "ikea": "Shopping",
    "clothing store": "Shopping",
    "furniture shop": "Shopping",
    "mobile repair": "Shopping",
    "barber shop": "Shopping",
    # Entertainment
    "netflix": "Entertainment",
    "hotstar": "Entertainment",
    "youtube premium": "Entertainment",
    "spotify": "Entertainment",
    "amazon prime": "Entertainment",
    "disney": "Entertainment",
    "bookmyshow": "Entertainment",
    "pvr": "Entertainment",
    "inox": "Entertainment",
    "hotel stay": "Entertainment",
    "newspapers": "Entertainment",
    "newspaper digital": "Entertainment",
    # Utilities
    "electricity board": "Utilities",
    "electricity": "Utilities",
    "piped gas": "Utilities",
    "gas": "Utilities",
    "internet bill": "Utilities",
    "jio recharge": "Utilities",
    "jio": "Utilities",
    "airtel": "Utilities",
    "bsnl": "Utilities",
    "vi": "Utilities",
    "water bill": "Utilities",
    "wifi": "Utilities",
    # Healthcare
    "apollo pharmacy": "Healthcare",
    "medplus": "Healthcare",
    "netmeds": "Healthcare",
    "1mg": "Healthcare",
    "practo": "Healthcare",
    "dr consult fee": "Healthcare",
    "dentist fee": "Healthcare",
    "doctor": "Healthcare",
    "pharmacy": "Healthcare",
    "hospital": "Healthcare",
    "gym membership": "Healthcare",
    "cult.fit": "Healthcare",
    # Education
    "udemy course": "Education",
    "udemy": "Education",
    "coursera": "Education",
    "byju": "Education",
    "unacademy": "Education",
    "vedantu": "Education",
    "tuition fees": "Education",
    "school fees": "Education",
    "college fees": "Education",
    # Rent
    "rent-landlord": "Rent",
    "rent": "Rent",
    "house rent": "Rent",
    "pg rent": "Rent",
    # EMI / Loan
    "emi-hdfc loan": "EMI_Loan",
    "emi-hdfc personal loan": "EMI_Loan",
    "emi-bajaj finance": "EMI_Loan",
    "emi": "EMI_Loan",
    "loan emi": "EMI_Loan",
    "home loan": "EMI_Loan",
    "car loan": "EMI_Loan",
    # Savings / Investment
    "groww-mf": "Savings_Investment",
    "groww": "Savings_Investment",
    "zerodha sip": "Savings_Investment",
    "zerodha": "Savings_Investment",
    "ppf": "Savings_Investment",
    "fd": "Savings_Investment",
    "mutual fund": "Savings_Investment",
    "investment": "Savings_Investment",
    "sip": "Savings_Investment",
    "nps": "Savings_Investment",
    "lic premium": "Savings_Investment",
    "lic": "Savings_Investment",
    # Salary / Income
    "salary": "Salary",
    "salary corp": "Salary",
    "neft salary": "Salary",
    "salary corp neft": "Salary",
    "acme pvtltd": "Salary",
    "salary-infosys": "Salary",
    "freelance payment": "Salary",
    "cashback-amazon": "Salary",   # cashback = income-like
    "cashback-hdfc-cc": "Salary",
    "cashback": "Salary",
    # Transfers
    "transfer": "Transfer",
    "upi": "Transfer",
    "neft": "Transfer",
    "imps": "Transfer",
    "rtgs": "Transfer",
    "cc payment": "Transfer",
    "wedding gift upi": "Transfer",
    # ATM
    "atm": "ATM",
    # Insurance (treat as savings-adjacent)
    "insurance": "Savings_Investment",
    "star health": "Savings_Investment",
    "max bupa": "Savings_Investment",
}

# In-memory cache: merchant_name_lower -> (category, method, confidence)
_CACHE: dict[str, tuple[str, str, float]] = {}


# ---------------------------------------------------------------------------
# Output model
# ---------------------------------------------------------------------------

@dataclass
class CategorisedTransaction:
    """ParsedTransaction enriched with a category."""
    # Copy from ParsedTransaction
    id: str
    raw_message: str
    amount: Optional[float]
    transaction_type: Optional[str]
    merchant: Optional[str]
    vpa: Optional[str]
    date: Optional[str]
    balance: Optional[float]
    bank: Optional[str]
    parse_method: str
    confidence: float
    # New fields
    category: str
    category_method: str   # "lookup" | "llm" | "default"
    category_confidence: float

    @classmethod
    def from_parsed(
        cls,
        txn: ParsedTransaction,
        category: str,
        category_method: str,
        category_confidence: float,
    ) -> "CategorisedTransaction":
        return cls(
            id=txn.id,
            raw_message=txn.raw_message,
            amount=txn.amount,
            transaction_type=txn.transaction_type,
            merchant=txn.merchant,
            vpa=txn.vpa,
            date=txn.date,
            balance=txn.balance,
            bank=txn.bank,
            parse_method=txn.parse_method,
            confidence=txn.confidence,
            category=category,
            category_method=category_method,
            category_confidence=category_confidence,
        )


# ---------------------------------------------------------------------------
# Lookup logic
# ---------------------------------------------------------------------------

def _lookup(merchant: str) -> Optional[str]:
    """Check merchant against lookup table. Returns category or None."""
    key = merchant.strip().lower()
    # Exact match
    if key in MERCHANT_LOOKUP:
        return MERCHANT_LOOKUP[key]
    # Partial match (merchant contains a known key or vice versa)
    for known, cat in MERCHANT_LOOKUP.items():
        if known in key or key in known:
            return cat
    return None


def _llm_categorise(merchant: str, txn: ParsedTransaction, adapter) -> tuple[str, float]:
    """Ask LLM to categorise an unknown merchant."""
    from llm.prompts import CATEGORISE_PROMPT_V1
    from llm.schemas import MerchantCategoryLLM
    try:
        prompt = CATEGORISE_PROMPT_V1.format(
            merchant=merchant,
            transaction_type=txn.transaction_type or "unknown",
            amount=txn.amount or 0,
        )
        result: MerchantCategoryLLM = adapter.generate(
            prompt=prompt,
            response_schema=MerchantCategoryLLM,
            temperature=0.1,
        )
        cat = result.category
        if cat not in VALID_CATEGORIES:
            logger.warning("LLM returned invalid category %r for merchant %r", cat, merchant)
            return "Other", 0.3
        return cat, result.confidence
    except Exception as exc:
        logger.warning("LLM categorise failed for %r: %s", merchant, exc)
        return "Other", 0.0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def categorise(txn: ParsedTransaction, adapter=None) -> CategorisedTransaction:
    """Categorise a single transaction.

    Args:
        txn: Parsed transaction.
        adapter: LLM adapter for unknown-merchant fallback.

    Returns:
        CategorisedTransaction with category and category_method.
    """
    merchant = (txn.merchant or "").strip()

    # Special case: credit == salary if merchant looks like it
    if txn.transaction_type == "credit" and not merchant:
        return CategorisedTransaction.from_parsed(txn, "Transfer", "default", 0.5)

    if not merchant:
        return CategorisedTransaction.from_parsed(txn, "Other", "default", 0.0)

    cache_key = merchant.lower()
    if cache_key in _CACHE:
        cat, method, conf = _CACHE[cache_key]
        return CategorisedTransaction.from_parsed(txn, cat, method + "_cached", conf)

    # 1. Lookup table
    cat = _lookup(merchant)
    if cat:
        _CACHE[cache_key] = (cat, "lookup", 1.0)
        return CategorisedTransaction.from_parsed(txn, cat, "lookup", 1.0)

    # 2. LLM fallback
    if adapter is not None:
        cat, conf = _llm_categorise(merchant, txn, adapter)
        _CACHE[cache_key] = (cat, "llm", conf)
        return CategorisedTransaction.from_parsed(txn, cat, "llm", conf)

    # 3. Default
    _CACHE[cache_key] = ("Other", "default", 0.0)
    return CategorisedTransaction.from_parsed(txn, "Other", "default", 0.0)


def categorise_transactions(
    txns: list[ParsedTransaction], adapter=None
) -> list[CategorisedTransaction]:
    """Categorise a list of transactions."""
    return [categorise(t, adapter=adapter) for t in txns]
