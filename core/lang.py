"""
core/lang.py — language detection and query normalisation for English / Hindi / Hinglish.

Users type money questions in three ways:
  en  : "What is a SIP?"
  hg  : "SIP kya hota hai aur kaise start karte hain?"   (Hindi in Roman script)
  hi  : "SIP क्या होता है?"                                (Devanagari)

Retrieval runs over English text, so `expand_query` appends English equivalents of the
Hindi/Hinglish words. No network or LLM needed.

Public API:
  detect_language(text) -> "en" | "hg" | "hi"
  tokenize(text) -> list[str]
  expand_query(text) -> str
"""

from __future__ import annotations

import re

_TOKEN_RE = re.compile(r"[ऀ-ॿ]+|[a-z0-9&]+")
_DEVANAGARI_RE = re.compile(r"[ऀ-ॿ]")

# Roman-script Hindi words that rarely occur in English text.
_HINGLISH_MARKERS = {
    "kya", "kaise", "kaisa", "kaun", "kab", "kahan", "kitna", "kitni", "kitne", "hai", "hain",
    "hota", "hoti", "hote", "karun", "karu", "karna", "karein", "karen", "chahiye", "nahi",
    "nahin", "mein", "me", "ka", "ki", "ke", "ko", "se", "par", "aur", "mera", "meri", "mere",
    "maine", "mujhe", "tum", "aap", "paisa", "paise", "bachat", "nivesh", "byaj", "karz",
    "udhaar", "bima", "kharcha", "kharch", "mehngai", "sahi", "safe", "lena", "dena", "chukayein",
    "badhayein", "banayein", "rakhna", "rakhein", "wala", "wale", "agar", "toh", "to", "bhi",
    "kuch", "sab", "zyada", "kam", "pehle", "baad", "jaldi", "abhi", "kyu", "kyun", "lagta",
    "lagana", "milta", "milti", "sakta", "sakte", "sakti", "raha", "rahi", "gaya", "gayi",
}

# Words that are ambiguous with English; only count when 2+ other markers are present.
_WEAK = {"to", "me", "safe", "par", "se", "ka", "ki", "ke", "ko", "sab", "kam"}

_EXPANSIONS: dict[str, str] = {
    # --- Hinglish -> English
    "bachat": "savings save", "bachana": "save savings", "bachayein": "save savings",
    "nivesh": "invest investment", "invest": "invest investment", "paisa": "money",
    "paise": "money", "byaj": "interest", "karz": "loan debt", "karza": "loan debt",
    "udhaar": "loan debt borrow", "bima": "insurance", "mehngai": "inflation",
    "kharcha": "spending expense", "kharch": "spending expense", "fizool": "impulse spending",
    "kamai": "income earn", "kiraya": "rent", "ghar": "house home", "sona": "gold",
    "girne": "fall crash", "gir": "fall crash", "chhoot": "deduction exemption",
    "chhut": "deduction exemption", "dhokha": "fraud scam", "thagi": "fraud scam",
    "nuksan": "loss", "faida": "profit", "kitna": "how much", "kab": "when",
    "kahan": "where", "kaise": "how", "kya": "what", "kyu": "why", "kyun": "why",
    "pehli": "first", "naukri": "job", "kaun": "which", "chukayein": "repay pay off",
    "chukana": "repay pay off", "badhayein": "improve increase", "sasta": "cheap low cost",
    "mehnga": "expensive", "bhari": "pay", "bharna": "pay", "bharo": "pay",
    "galtiyan": "mistakes", "salana": "annual yearly", "mahine": "monthly month",
    "mahina": "monthly month", "tax": "tax", "chhoti": "small", "bada": "big large",
    "lagta": "charged", "lagana": "invest put", "milta": "get receive",
    # --- Hindi (Devanagari) -> English
    "बचत": "savings save", "निवेश": "invest investment", "कर": "tax", "टैक्स": "tax",
    "बीमा": "insurance", "इंश्योरेंस": "insurance", "ब्याज": "interest",
    "कर्ज़": "loan debt", "कर्ज": "loan debt", "लोन": "loan", "महंगाई": "inflation",
    "क्रेडिट": "credit", "स्कोर": "score", "कार्ड": "card", "खाता": "account",
    "खाते": "account", "सोना": "gold", "सोने": "gold", "शेयर": "share stock",
    "बाज़ार": "market", "बाजार": "market", "गिरने": "fall crash", "सैलरी": "salary",
    "वेतन": "salary", "किराये": "rent", "किराया": "rent", "घर": "house home",
    "पेंशन": "pension", "म्यूचुअल": "mutual", "फंड": "fund", "डीमैट": "demat",
    "नॉमिनी": "nominee", "फ्रीलांस": "freelance", "छूट": "deduction exemption",
    "गारंटीड": "guaranteed", "रिटर्न": "returns", "ठगी": "fraud scam", "धोखा": "fraud scam",
    "आपातकालीन": "emergency", "टर्म": "term", "हेल्थ": "health", "क्रिप्टो": "crypto",
    "ऑप्शन": "options", "खर्च": "spending expense", "बजट": "budget", "पहली": "first",
    "नौकरी": "job", "कैसे": "how", "क्या": "what", "महीने": "monthly month",
    "ग्रेच्युटी": "gratuity", "एनपीएस": "nps", "पीपीएफ": "ppf", "रिजीम": "regime",
    "नया": "new", "पुराना": "old", "अंतर": "difference", "फर्क": "difference",
    "कितना": "how much", "कितनी": "how much", "सुरक्षित": "safe", "जोखिम": "risk",
    "क्रेडिट": "credit", "ईएमआई": "emi", "डाउन": "down", "पेमेंट": "payment",
    "मिनिमम": "minimum", "बैलेंस": "balance", "रिटायरमेंट": "retirement",
    "सुकन्या": "sukanya", "समृद्धि": "samriddhi", "नेट": "net", "वर्थ": "worth",
    "चक्रवृद्धि": "compound compounding", "आदत": "habit", "गलतियां": "mistakes",
    "छुटकारा": "get rid pay off", "परेशान": "harass harassment", "बैंक": "bank",
    "आईटीआर": "itr income tax return file", "भरें": "file pay", "भरना": "file pay",
    "पॉकेट": "pocket", "मनी": "money", "डायरेक्ट": "direct", "रेगुलर": "regular",
    "प्लान": "plan", "बांटें": "allocation split diversify", "बांटना": "allocation split diversify",
    "वादा": "promise guaranteed", "स्कीम": "scheme", "लक्ष्य": "goal", "इक्विटी": "equity",
    "डेट": "debt", "मैनेज": "manage budget", "छोड़ें": "stop control", "ज़्यादा": "more excess",
    "होम": "home", "मिल": "get", "कर्ज़ा": "loan debt", "रखें": "keep", "कहां": "where",
    "डूब": "fail sink", "सलाहकार": "adviser advisor", "योजना": "scheme plan",
}


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def detect_language(text: str) -> str:
    """'hi' if mostly Devanagari, 'hg' if Roman-script Hindi markers dominate, else 'en'."""
    if not text:
        return "en"
    letters = [c for c in text if c.isalpha()]
    if letters and sum(1 for c in letters if _DEVANAGARI_RE.match(c)) / len(letters) > 0.3:
        return "hi"
    toks = tokenize(text)
    strong = sum(1 for t in toks if t in _HINGLISH_MARKERS and t not in _WEAK)
    weak = sum(1 for t in toks if t in _WEAK)
    if strong >= 2 or (strong >= 1 and weak >= 1 and len(toks) <= 8):
        return "hg"
    return "en"


def expand_query(text: str) -> str:
    """Original text plus English equivalents of any Hindi/Hinglish words."""
    extra = [_EXPANSIONS[t] for t in tokenize(text) if t in _EXPANSIONS]
    return (text + " " + " ".join(extra)).strip()
