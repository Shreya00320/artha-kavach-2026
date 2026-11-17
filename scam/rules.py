"""
scam/rules.py — Rule-based scam detector.

Checks SMS/WhatsApp messages against keyword and regex patterns:
  - Urgency pressure language
  - OTP / PIN requests
  - Suspicious / phishing links
  - UPI collect-request scam
  - KYC expiry threats
  - Lottery / prize / winning scams
  - Job fee / registration fee scams
  - Fee-to-claim (processing fee, stamp duty, GST to get money)
  - Authority impersonation (RBI, NPCI, Income Tax, Cyber Crime)

Returns a RulesResult with aggregated score (0–1) and all matched rules.
Score is NOT a simple sum — it is the max of a weighted combination so a
single very strong rule can't push score past the cap without corroboration.

Public API:
  run_rules(text: str) -> RulesResult
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import NamedTuple


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class RuleMatch:
    """A single matched rule."""
    rule_id: str
    name: str
    category: str
    matched_text: str   # the substring that triggered the rule
    weight: float       # 0–1 severity of this individual rule


@dataclass
class RulesResult:
    """Output of the rule-based detector."""
    score: float                    # 0–1 aggregated scam score
    matches: list[RuleMatch] = field(default_factory=list)
    n_rules_matched: int = 0
    top_category: str = ""          # most-matched category


# ---------------------------------------------------------------------------
# Rule definitions
# ---------------------------------------------------------------------------

class Rule(NamedTuple):
    rule_id: str
    name: str
    category: str
    pattern: re.Pattern
    weight: float


def _p(pattern: str) -> re.Pattern:
    return re.compile(pattern, re.IGNORECASE)


# OTP / PIN requests  — weight 0.9 (very strong signal)
OTP_PIN_RULES: list[Rule] = [
    Rule("R001", "Share OTP request", "otp_request",
         _p(r"\b(share|send|give|batao|dena|bata|enter)\b.{0,30}\botp\b"), 0.9),
    Rule("R002", "Share PIN request", "otp_request",
         _p(r"\b(share|send|give|batao|dena|enter)\b.{0,30}\b(pin|password)\b"), 0.9),
    Rule("R003", "OTP to receive money", "otp_request",
         _p(r"\botp\b.{0,40}\b(receive|claim|refund|prize|money|transfer)\b"), 0.9),
    Rule("R004", "Verify OTP / account verification OTP", "otp_request",
         _p(r"\bverif(y|ication)\b.{0,20}\botp\b"), 0.7),
]

# UPI collect-request scams — weight 0.85
COLLECT_REQUEST_RULES: list[Rule] = [
    Rule("R010", "Collect request language", "collect_request",
         _p(r"\bcollect\s*request\b"), 0.85),
    Rule("R011", "Accept/approve to receive money", "collect_request",
         _p(r"\b(accept|approve)\b.{0,40}\b(receive|get|claim)\b.{0,20}\b(money|refund|amount|rs|rupee)\b"), 0.85),
    Rule("R012", "Re 1 verification trick", "collect_request",
         _p(r"\b(re\.?\s*1|rs\.?\s*1|rupee\s*1|1\s*rupee)\b.{0,40}\b(verif|check|test|confirm)\b"), 0.9),
    Rule("R013", "PIN to receive refund", "collect_request",
         _p(r"\b(pin|upi\s*pin)\b.{0,30}\b(receive|get|claim|refund)\b"), 0.95),
]

# Urgency / pressure language — weight 0.5–0.65
URGENCY_RULES: list[Rule] = [
    Rule("R020", "Account block/suspend urgency", "urgency",
         _p(r"\b(account|sim|number|service)\b.{0,40}\b(block|suspend|deactivat|clos|band)\b.{0,30}\b(hour|minute|day|aaj|abhi|immediately|turant)\b"), 0.65),
    Rule("R021", "Generic urgency - immediate action", "urgency",
         _p(r"\b(immediately|urgent|urgently|last\s*chance|act\s*now|expire\s*tonight|abhi\s*karein|turant)\b"), 0.5),
    Rule("R022", "Time pressure (X hours/minutes)", "urgency",
         _p(r"\b(within|in|next)\b.{0,10}\b\d+\s*(hour|minute|ghante|minute)\b"), 0.5),
    Rule("R023", "Arrest / legal threat", "urgency",
         _p(r"\b(arrested?|legal\s*action|court|case\s*filed|fir|warrant)\b"), 0.7),
    Rule("R024", "Electricity cut threat", "urgency",
         _p(r"\b(electricity|power|bijli)\b.{0,30}\b(cut|disconnect|band)\b"), 0.6),
]

# KYC fraud — weight 0.6–0.75
KYC_RULES: list[Rule] = [
    Rule("R030", "KYC expiry threat", "kyc_fraud",
         _p(r"\bkyc\b.{0,40}\b(expir|incomplet|updat|verif|pending)\b"), 0.7),
    Rule("R031", "KYC via link", "kyc_fraud",
         _p(r"\bkyc\b.{0,60}\b(click|link|http|visit|url)\b"), 0.75),
    Rule("R032", "KYC + account block", "kyc_fraud",
         _p(r"\bkyc\b.{0,60}\b(block|suspend|band|deactivat)\b"), 0.75),
]

# Phishing links — weight 0.7–0.85
PHISHING_RULES: list[Rule] = [
    Rule("R040", "URL shortener in SMS", "phishing_link",
         _p(r"\b(bit\.ly|tinyurl|t\.co|goo\.gl|is\.gd|short\.gy)\b"), 0.8),
    Rule("R041", "Suspicious TLD", "phishing_link",
         _p(r"https?://[\w\-]+\.(ml|tk|xyz|click|site|cf|ga|gq|pw|top|icu|live|online)(/|\s|$)"), 0.85),
    Rule("R042", "Bank name in unofficial domain", "phishing_link",
         _p(r"https?://[\w\-]*(sbi|hdfc|icici|axis|paytm|npci|rbi|uidai|income.?tax)[\w\-]*\.(ml|xyz|click|site|in\b(?!\.)|com(?!\s*—))\b"), 0.85),
    Rule("R043", "Official-looking fake domain", "phishing_link",
         _p(r"https?://[\w\-]+(kyc|update|verify|secure|refund|claim|reward|portal)[\w\-]*\.\w+"), 0.7),
]

# Lottery / prize / winning — weight 0.75
LOTTERY_RULES: list[Rule] = [
    Rule("R050", "Won a prize / lottery", "lottery_scam",
         _p(r"\b(won|win|winner|jeeta|lucky\s*draw|lottery|prize|badhai)\b.{0,60}\b(rs|rupee|lakh|crore|\d{3,})\b"), 0.75),
    Rule("R051", "NPCI / government lottery claim", "lottery_scam",
         _p(r"\b(npci|rbi|government|govt)\b.{0,40}\b(lottery|lucky\s*draw|prize|winner)\b"), 0.85),
    Rule("R052", "Processing fee to claim prize", "lottery_scam",
         _p(r"\b(processing\s*fee|stamp\s*duty|gst\s*charge|courier\s*charge|tax\s*clearance)\b.{0,40}\b(claim|prize|reward|refund|win)\b"), 0.9),
]

# Job / registration fee scams — weight 0.75
JOB_SCAM_RULES: list[Rule] = [
    Rule("R060", "Registration fee for job", "job_scam",
         _p(r"\b(registration|joining|training|kit|material)\s*fee\b"), 0.8),
    Rule("R061", "Pay to work / earn", "job_scam",
         _p(r"\b(pay|deposit|send)\b.{0,20}\b(rs|rupee|\d+)\b.{0,40}\b(job|earn|work\s*from\s*home|wfh|part.?time)\b"), 0.75),
    Rule("R062", "Unrealistic WFH earning", "job_scam",
         _p(r"\b(earn|income|salary)\b.{0,25}\b(rs\.?\s*[\d,]{4,}|lakh)\b.{0,35}\b(month|daily|home|ghar)\b"), 0.55),
]

# Authority impersonation — weight 0.65–0.8
IMPERSONATION_RULES: list[Rule] = [
    Rule("R070", "RBI contacting about account", "impersonation",
         _p(r"\brbi\b.{0,60}\b(account|block|suspend|verif|kyc|money|transfer|otp)\b"), 0.75),
    Rule("R071", "Cyber Crime / police threat", "impersonation",
         _p(r"\b(cyber\s*crime|police|officer|cbi|ed\b|enforcement)\b.{0,40}\b(call|contact|arrested?|case)\b"), 0.7),
    Rule("R072", "Income Tax refund via link", "impersonation",
         _p(r"\b(income\s*tax|it\s*refund|itr)\b.{0,60}\b(click|link|http|visit|enter)\b"), 0.8),
    Rule("R073", "TRAI SIM suspension threat", "impersonation",
         _p(r"\b(trai|telecom)\b.{0,40}\b(suspend|block|deactivat|mobile)\b"), 0.7),
]

# Remote access scams — weight 0.9
REMOTE_ACCESS_RULES: list[Rule] = [
    Rule("R080", "Install remote access app", "remote_access",
         _p(r"\b(install|download)\b.{0,40}\b(anydesk|teamviewer|quicksupport|screenshare|remote)\b"), 0.9),
    Rule("R081", "Screen share request", "remote_access",
         _p(r"\b(share\s*screen|screen\s*shar|remote\s*access)\b"), 0.85),
]

# Fee to receive money — weight 0.85
FEE_TO_RECEIVE_RULES: list[Rule] = [
    Rule("R090", "Pay fee to receive money", "fee_to_receive",
         _p(r"\b(pay|send|bhej|deposit)\b.{0,20}\b(rs\.?\s*\d+|\d+\s*rs)\b.{0,40}\b(receive|claim|refund|get|release|disburse)\b"), 0.85),
    Rule("R091", "Processing fee for loan", "fee_to_receive",
         _p(r"\b(processing\s*fee|stamp\s*duty|insurance\s*charge)\b.{0,40}\b(loan|disburse|sanction|approve)\b"), 0.85),
]

# Suspicious VPA / recipient — weight 0.6
SUSPICIOUS_VPA_RULES: list[Rule] = [
    Rule("R100", "Suspicious UPI collect VPA", "suspicious_vpa",
         _p(r"\b(fraud|refund|cashback|prize|winner|claim|lottery)[\w\-]*@\w+"), 0.8),
    Rule("R101", "Generic personal VPA for business claim", "suspicious_vpa",
         _p(r"\b(prize|reward|refund|cashback)[\w]*@(okaxis|oksbi|okhdfcbank|okicici|ybl|ibl)\b"), 0.75),
]

# Digital arrest / courier-parcel impersonation — weight 0.85–0.9
# (I4C/MHA advisories: police, CBI, ED or customs never "arrest" anyone over a video call)
DIGITAL_ARREST_RULES: list[Rule] = [
    Rule("R110", "Digital arrest threat", "digital_arrest",
         _p(r"\b(digital(ly)?\s*arrest|video\s*call\b.{0,40}\b(arrest|investigation|statement|police|cbi|customs)|"
            r"(arrest|investigation)\b.{0,40}\bvideo\s*call)"), 0.9),
    Rule("R111", "Parcel with illegal items", "digital_arrest",
         _p(r"\b(parcel|package|courier|consignment|fedex|dhl)\b.{0,60}\b(drugs?|narcotic|mdma|illegal|seized|contraband|passports?)\b"), 0.85),
    Rule("R112", "Money laundering / Aadhaar misuse accusation", "digital_arrest",
         _p(r"\b(money\s*laundering|hawala|aadhaar\b.{0,30}\b(misuse|used|linked)\b.{0,40}\b(crime|case|laundering|illegal|fraud|account))"), 0.8),
]

# Malicious app install (APK) — weight 0.85
MALICIOUS_APP_RULES: list[Rule] = [
    Rule("R120", "APK file / app outside Play Store", "malicious_app",
         _p(r"(\.apk\b|\bapk\s*(file|download|link)\b)"), 0.85),
    # Weaker on its own: legitimate apps also say "download our app"
    Rule("R121", "Install an app from a link", "malicious_app",
         _p(r"\b(install|download)\b.{0,30}\b(this|our|the)?\s*app\b.{0,30}\b(link|whatsapp|below|here)\b"), 0.45),
]

# QR-code-to-receive trick — weight 0.9
QR_RULES: list[Rule] = [
    Rule("R130", "Scan QR to receive money", "qr_scam",
         _p(r"\bscan\b.{0,30}\bqr\b.{0,40}\b(receive|get|claim|refund|payment\s*will|credit)"), 0.9),
]

# Task / investment group scams — weight 0.6–0.85
INVESTMENT_TASK_RULES: list[Rule] = [
    Rule("R140", "Paid tasks (like/review/rate) for money", "task_scam",
         _p(r"\b(like|subscribe|rate|review|follow)\b.{0,30}\b(videos?|hotels?|products?|channels?|posts?)\b.{0,50}\b(earn|paid|rs|₹|income|commission)"), 0.8),
    Rule("R141", "Guaranteed / unrealistic returns", "investment_scam",
         _p(r"\b(guaranteed|assured|fixed)\b.{0,20}\b(returns?|profit|income)\b|\b(double|triple)\s+(your\s+)?money\b|\b\d{2,3}\s*%\s*(returns?|profit)\b.{0,30}\b(month|week|days?)"), 0.8),
    Rule("R142", "Stock tips / trading group invite", "investment_scam",
         _p(r"\b(stock|share|ipo|trading|crypto)\b.{0,40}\b(tips?|group|vip|signals?)\b.{0,40}\b(join|whatsapp|telegram|link)"), 0.65),
]

# "Sent by mistake" / fake payment refund trick — weight 0.7
MISTAKEN_TRANSFER_RULES: list[Rule] = [
    Rule("R150", "Money 'sent by mistake' — return request", "mistaken_transfer",
         _p(r"\b(sent|transferred|credited|galti\s*se)\b.{0,40}\b(by\s*mistake|wrongly|galti|accidentally)\b.{0,60}\b(return|send\s*back|wapas|refund)"), 0.7),
]

# Hinglish variants of the strongest signals
HINGLISH_RULES: list[Rule] = [
    Rule("R160", "OTP share karne ko kehna (Hinglish)", "otp_request",
         _p(r"\botp\b.{0,25}\b(bata|batao|bhej|bhejo|bhejein|daal|daalo|dijiye|share\s*kar|de\s*do|dein)\b"), 0.9),
    Rule("R161", "Account band hone ki dhamki (Hinglish)", "urgency",
         _p(r"\b(khata|account|sim)\b.{0,30}\b(band|block)\b.{0,20}\b(ho\s*jayega|hone\s*wala|kar\s*diya\s*jayega)"), 0.7),
    Rule("R162", "Inaam / lottery jeetna (Hinglish)", "lottery_scam",
         _p(r"\b(inaam|inam|lottery)\b.{0,40}\b(jeet|jeeta|jeeti|jeete|mila|laga)"), 0.5),
    Rule("R163", "Bank details maangna (Hinglish)", "otp_request",
         _p(r"\b(net\s*banking|card|cvv|pin|password|bank)\s*(details?|number)?\b.{0,20}\b(dijiye|bhejiye|batayein|share\s*karein|bhejo|batao)\b"), 0.85),
]

ALL_RULES: list[Rule] = (
    OTP_PIN_RULES + COLLECT_REQUEST_RULES + URGENCY_RULES + KYC_RULES +
    PHISHING_RULES + LOTTERY_RULES + JOB_SCAM_RULES + IMPERSONATION_RULES +
    REMOTE_ACCESS_RULES + FEE_TO_RECEIVE_RULES + SUSPICIOUS_VPA_RULES +
    DIGITAL_ARREST_RULES + MALICIOUS_APP_RULES + QR_RULES + INVESTMENT_TASK_RULES +
    MISTAKEN_TRANSFER_RULES + HINGLISH_RULES
)


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _aggregate_score(matches: list[RuleMatch]) -> float:
    """Combine individual rule weights into a final 0–1 score.

    Uses: score = 1 - product(1 - w_i) for all matched rules
    This is the "noisy-OR" combination: each rule independently tries
    to push the score toward 1, but no single rule dominates.
    """
    if not matches:
        return 0.0
    result = 1.0
    for m in matches:
        result *= (1.0 - m.weight)
    return round(1.0 - result, 4)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_rules(text: str) -> RulesResult:
    """Run all scam detection rules against a message.

    Args:
        text: Raw SMS / WhatsApp message text.

    Returns:
        RulesResult with score, matched rules, and top category.
    """
    matches: list[RuleMatch] = []
    for rule in ALL_RULES:
        m = rule.pattern.search(text)
        if m:
            matches.append(RuleMatch(
                rule_id=rule.rule_id,
                name=rule.name,
                category=rule.category,
                matched_text=m.group(0).strip(),
                weight=rule.weight,
            ))

    score = _aggregate_score(matches)

    # Find most-matched category
    from collections import Counter
    cat_counts = Counter(m.category for m in matches)
    top_cat = cat_counts.most_common(1)[0][0] if cat_counts else ""

    return RulesResult(
        score=score,
        matches=matches,
        n_rules_matched=len(matches),
        top_category=top_cat,
    )
