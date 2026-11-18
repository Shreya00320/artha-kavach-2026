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
import re
from dataclasses import dataclass, replace
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
    "Refund",   # credits that reverse a purchase — netted off spending, never income
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

MERCHANT_LOOKUP.update({
    # Food / groceries / quick commerce
    "instamart": "Food", "swiggy instamart": "Food", "bb daily": "Food", "jiomart": "Food",
    "licious": "Food", "eatsure": "Food", "chaayos": "Food", "burger king": "Food",
    "subway": "Food", "canteen": "Food", "mess": "Food", "tiffin": "Food",
    "milk": "Food", "dairy": "Food", "kirana": "Food", "grocery": "Food",
    # Transport
    "namma yatri": "Transport", "blusmart": "Transport", "indigo": "Transport",
    "air india": "Transport", "fastag": "Transport", "parking fee": "Transport",
    "parking": "Transport", "hp petrol": "Transport", "indian oil": "Transport",
    "bharat petroleum": "Transport", "yulu": "Transport", "auto": "Transport",
    # Shopping
    "amazon pay": "Shopping", "reliance digital": "Shopping", "nykaa fashion": "Shopping",
    "snapdeal": "Shopping", "firstcry": "Shopping", "zudio": "Shopping", "westside": "Shopping",
    # Entertainment / subscriptions
    "jiocinema": "Entertainment", "jiohotstar": "Entertainment", "sonyliv": "Entertainment",
    "zee5": "Entertainment", "prime video": "Entertainment", "apple.com/bill": "Entertainment",
    "apple music": "Entertainment", "google play": "Entertainment", "gaana": "Entertainment",
    "steam": "Entertainment", "dream11": "Entertainment", "amazon subscribe": "Entertainment",
    "chatgpt": "Entertainment", "openai": "Entertainment", "linkedin premium": "Entertainment",
    # Utilities and household services
    "bescom": "Utilities", "tata power": "Utilities", "adani electricity": "Utilities",
    "mseb": "Utilities", "act fibernet": "Utilities", "broadband": "Utilities",
    "dth": "Utilities", "tata play": "Utilities", "recharge": "Utilities",
    "plumber": "Utilities", "electrician": "Utilities", "maid": "Utilities",
    "society maintenance": "Utilities", "maintenance": "Utilities", "laundry": "Utilities",
    # Healthcare / fitness
    "pharmeasy": "Healthcare", "tata 1mg": "Healthcare", "lab test": "Healthcare",
    "clinic": "Healthcare", "cultfit": "Healthcare", "gym": "Healthcare",
    # Education
    "physics wallah": "Education", "upgrad": "Education", "great learning": "Education",
    "exam fee": "Education", "books": "Education",
    # Savings / investment / insurance
    "kuvera": "Savings_Investment", "coin by zerodha": "Savings_Investment",
    "paytm money": "Savings_Investment", "indmoney": "Savings_Investment",
    "elss": "Savings_Investment", "recurring deposit": "Savings_Investment",
    "sukanya": "Savings_Investment", "digital gold": "Savings_Investment",
    "care health": "Savings_Investment", "niva bupa": "Savings_Investment",
    "hdfc ergo": "Savings_Investment", "acko": "Savings_Investment",
    "term insurance": "Savings_Investment",
    # Credit card bills are transfers (the spend was already counted on the card)
    "credit card bill": "Transfer", "cred": "Transfer",
    # Pay-later = borrowing
    "bnpl": "EMI_Loan", "simpl": "EMI_Loan", "lazypay": "EMI_Loan", "slice": "EMI_Loan",
    # Income-like
    "interest credit": "Salary", "int.pd": "Salary", "stipend": "Salary",
})

# Subscription merchants (used by the subscription tracker)
SUBSCRIPTION_MERCHANTS = {
    "netflix", "hotstar", "jiohotstar", "jiocinema", "youtube premium", "spotify",
    "amazon prime", "prime video", "sonyliv", "zee5", "apple music", "apple.com/bill",
    "google play", "gaana", "linkedin premium", "chatgpt", "openai", "cult.fit",
    "cultfit", "gym membership", "newspaper digital", "amazon subscribe", "tata play",
    "act fibernet", "broadband", "jio recharge", "airtel",
}

# Brand names commonly embedded in merchant UPI handles ("swiggy.stores@axb").
_VPA_BRAND_HINTS = [
    "swiggy", "zomato", "zepto", "blinkit", "bigbasket", "uber", "ola", "rapido",
    "irctc", "amazon", "flipkart", "myntra", "meesho", "nykaa", "ajio", "netflix",
    "spotify", "hotstar", "bookmyshow", "jio", "airtel", "bescom", "zerodha",
    "groww", "kuvera", "apollo", "pharmeasy", "1mg", "dominos", "mcdonalds",
    "starbucks", "dmart", "makemytrip", "redbus", "cred", "lic",
]

# Payment-gateway / aggregator handles: the real brand is not in the VPA.
_GATEWAY_HINTS = ("razorpay", "payu", "cashfree", "billdesk", "ccavenue", "paytmqr",
                  "bharatpe", "pinelabs", "juspay")


def resolve_merchant(merchant: Optional[str], vpa: Optional[str]) -> Optional[str]:
    """Turn a raw UPI handle into a readable merchant name when possible.

    "swiggy.stores@axb" -> "Swiggy";  "razorpay.xyz@icici" -> "Razorpay merchant".
    Returns the original merchant if nothing better is known.
    """
    handle = (vpa or "").lower()
    if not handle and merchant and "@" in merchant:
        handle = merchant.lower()
    if not handle:
        return merchant
    local = handle.split("@")[0]
    for brand in _VPA_BRAND_HINTS:
        if re.search(rf"(^|[^a-z]){re.escape(brand)}([^a-z]|$)", local):
            return brand.upper() if brand in ("irctc", "lic") else brand.capitalize()
    for g in _GATEWAY_HINTS:
        if g in local:
            return f"{g.capitalize()} merchant"
    return merchant


_PHONE_VPA = re.compile(r"^(\+?91)?[6-9]\d{9}(-\d+)?$")
_PERSON_VPA = re.compile(r"^[a-z]{2,}[._][a-z]{2,}\d{0,4}$")
_BUSINESS_WORDS = ("store", "shop", "mart", "pay", "bill", "merchant", "pvt", "ltd",
                   "services", "enterprise", "traders", "foods", "cafe", "hotel")


def looks_like_person(merchant: Optional[str], vpa: Optional[str]) -> bool:
    """Heuristic P2P detector: phone-number VPAs and firstname.lastname VPAs.

    Money sent to friends and family is a transfer, not category spending —
    counting it as "Wants" is a common complaint about UPI expense trackers.
    """
    local = (vpa or "").split("@")[0].lower() if vpa else ""
    if not local and merchant:
        local = merchant.lower().strip()
    if not local:
        return False
    if _PHONE_VPA.match(local):
        return True
    if _PERSON_VPA.match(local):
        return not any(b in local for b in _VPA_BRAND_HINTS) and not any(
            w in local for w in _BUSINESS_WORDS
        )
    return False


_REFUND_RE = re.compile(r"\b(refund(ed)?|reversal|reversed|failed\s+txn|chargeback)\b", re.I)


_SALARY_RE = re.compile(r"\b(salary|sal\s*cr|payroll|stipend)\b", re.I)


def is_refund(txn: ParsedTransaction) -> bool:
    """A credit that returns money from a purchase (refund/reversal), not income."""
    if txn.transaction_type != "credit":
        return False
    return bool(_REFUND_RE.search(f"{txn.merchant or ''} {txn.raw_message or ''}"))


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

_KEYS_LONGEST_FIRST: list[str] = []


def _lookup(merchant: str) -> Optional[str]:
    """Check merchant against lookup table. Returns category or None."""
    key = re.sub(r"\s+", " ", merchant.strip().lower())
    if key in MERCHANT_LOOKUP:
        return MERCHANT_LOOKUP[key]
    # Whole-word match, longest known name first: "HOTSTAR PREMIUM" -> hotstar,
    # while "ACKO PREMIUM" no longer matches "emi" and "parent" no longer matches "rent".
    if len(_KEYS_LONGEST_FIRST) != len(MERCHANT_LOOKUP):
        _KEYS_LONGEST_FIRST[:] = sorted(MERCHANT_LOOKUP, key=len, reverse=True)
    for known in _KEYS_LONGEST_FIRST:
        if re.search(rf"(?<![a-z0-9]){re.escape(known)}(?![a-z0-9])", key):
            return MERCHANT_LOOKUP[known]
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
    # Refunds/reversals are credits that cancel a purchase — never income
    if is_refund(txn):
        return CategorisedTransaction.from_parsed(txn, "Refund", "rule", 0.9)

    resolved = resolve_merchant(txn.merchant, txn.vpa)
    if resolved and resolved != txn.merchant:
        txn = replace(txn, merchant=resolved)
    merchant = (txn.merchant or "").strip()

    # Person-to-person UPI (phone-number or firstname.lastname handle) = transfer
    if merchant and _lookup(merchant) is None and looks_like_person(merchant, txn.vpa):
        return CategorisedTransaction.from_parsed(txn, "Transfer", "p2p", 0.8)

    # Credits that mention salary/payroll anywhere in the SMS are income,
    # even when the bank template has no merchant field ("NEFT SALARY-INFOSYS").
    if txn.transaction_type == "credit" and _SALARY_RE.search(txn.raw_message or ""):
        return CategorisedTransaction.from_parsed(txn, "Salary", "rule", 0.9)

    # Special case: credit with no merchant at all
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
