"""scam/tactics.py – name the psychological tactic behind each matched scam rule.

Educational layer on top of the rules engine (ideas from Cialdini's *Influence* and
Kahneman's *Thinking, Fast and Slow*). Pure lookup, no scoring change.

  tactics_for(rule_result) -> list[dict(tactic, why, defence, rules)]
"""

TACTICS = {
    "Fake authority": (
        "Pretends to be police, CBI, RBI, a bank or a government office so you obey without thinking.",
        "Real agencies never arrest or interrogate over a call or video call. Hang up and call the official number yourself.",
        {"digital_arrest", "impersonation", "kyc_fraud"},
    ),
    "Urgency & fear": (
        "Rushes you so your slow, careful thinking never switches on.",
        "Pause for 60 seconds. Genuine banks do not demand action within minutes.",
        {"urgency", "otp_request"},
    ),
    "Greed & scarcity": (
        "Dangles a prize, a guaranteed return or a limited-time offer.",
        "If it sounds too good to be true it is. You never pay a fee to receive money.",
        {"lottery_scam", "investment_scam", "job_scam", "task_scam", "fee_to_receive"},
    ),
    "Trust hijack": (
        "Uses a familiar-looking link, app or payment request to borrow trust.",
        "Never tap unknown links, install remote-access apps, or approve a collect request to 'receive' money.",
        {"phishing_link", "malicious_app", "remote_access", "collect_request",
         "qr_scam", "suspicious_vpa", "mistaken_transfer"},
    ),
}


def tactics_for(rule_result) -> list[dict]:
    cats = {m.category for m in getattr(rule_result, "matches", [])}
    out = []
    for name, (why, defence, members) in TACTICS.items():
        hit = sorted(cats & members)
        if hit:
            out.append({"tactic": name, "why": why, "defence": defence, "rules": hit})
    return out
