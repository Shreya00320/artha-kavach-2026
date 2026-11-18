"""
scam/emergency.py — "I've been scammed — what now?" action plan and complaint draft.

Speed matters most: reporting within the first hours (the "golden hour") gives
the 1930 helpline the best chance of freezing money before it is moved on.
Content follows public guidance from I4C / cybercrime.gov.in, DoT's Sanchar
Saathi portal and RBI's 2017 customer-liability circular.

Nothing here contacts anyone — it produces a checklist and a text the victim
can paste into cybercrime.gov.in or read out on 1930.

Public API:
  SCAM_TYPES
  action_plan(scam_type, money_lost, hours_since) -> list[dict]
  complaint_draft(IncidentDetails) -> str
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

HELPLINE = "1930"
PORTAL = "https://cybercrime.gov.in"
CHAKSHU = "https://sancharsaathi.gov.in"   # 'Chakshu' — report fraud calls/SMS/WhatsApp
RBI_CMS = "https://cms.rbi.org.in"         # RBI complaint system, if the bank does not resolve

SCAM_TYPES = {
    "upi_collect": "UPI collect request / entered PIN to 'receive' money",
    "otp_shared": "Shared OTP / PIN / card details",
    "phishing_link": "Clicked a link and entered bank details",
    "remote_app": "Installed AnyDesk / TeamViewer / an APK",
    "digital_arrest": "'Digital arrest' — fake police / CBI / customs video call",
    "investment_task": "Investment, trading-group or online task scam",
    "job_loan": "Fake job, loan or lottery fee",
    "sim_swap": "SIM stopped working suddenly / SIM swap",
    "other": "Something else",
}


def action_plan(scam_type: str = "other", money_lost: bool = True, hours_since: Optional[float] = None) -> list[dict]:
    """Ordered checklist. Each step: {step, why, urgent}."""
    steps: list[dict] = []

    def add(step: str, why: str, urgent: bool = False) -> None:
        steps.append({"step": step, "why": why, "urgent": urgent})

    if money_lost:
        add(f"Call {HELPLINE} (National Cyber Crime Helpline) right now.",
            "Reported quickly, the transaction can be traced and the receiving account asked to hold the money. "
            "Every hour counts.", True)
        add("Call your bank's fraud line (the number on the back of your card or in the official app) "
            "and ask them to block the card / UPI / net banking and raise a fraud dispute.",
            "Under RBI's 2017 rules, if a fraud happened through no fault of yours and you report it within "
            "3 working days, your liability is zero. Delays increase what you may have to bear.", True)
    add(f"File a complaint at {PORTAL} (choose 'Report Financial Fraud') and note the acknowledgement number.",
        "The number is needed for your bank dispute and any police follow-up.", money_lost)

    specific = {
        "upi_collect": ("Open your UPI app → disable/deregister UPI, and change your UPI PIN from the official app.",
                        "Entering a UPI PIN always SENDS money — receiving never needs a PIN."),
        "otp_shared": ("Change net-banking password and card PIN from the official app/website; block cards you shared.",
                       "An OTP or PIN in someone else's hands lets them approve new payments."),
        "phishing_link": ("Change passwords for the bank and the e-mail linked to it; log out of all devices.",
                          "Phishing pages capture whatever you typed, including passwords."),
        "remote_app": ("Turn on airplane mode, uninstall AnyDesk/TeamViewer or the APK, then reset the phone if unsure.",
                       "Remote-access apps and malicious APKs can read OTPs and control your screen."),
        "digital_arrest": ("Disconnect the call. Do not pay. Police, CBI, ED or customs never arrest or "
                           "'investigate' anyone over a video call.",
                           "'Digital arrest' has no legal basis — it is pure intimidation."),
        "investment_task": ("Stop sending money — 'withdrawal fees' or 'taxes' to release profits are part of the scam.",
                            "These platforms show fake profits to pull in larger payments."),
        "job_loan": ("Do not pay any further 'fees'. Save the chat, the UPI IDs and phone numbers used.",
                     "Genuine employers and RBI-registered lenders never charge upfront fees to release money."),
        "sim_swap": ("Contact your mobile operator immediately to block the SIM, then your bank.",
                     "A swapped SIM lets fraudsters receive your OTPs."),
    }
    if scam_type in specific:
        add(*specific[scam_type], urgent=True)

    add("Save evidence: screenshots of messages, call logs, the scammer's numbers/UPI IDs, "
        "transaction IDs (UTR) and bank SMS.",
        "Complaints and bank disputes move faster with transaction references.")
    add(f"Report the number/message on Sanchar Saathi 'Chakshu' ({CHAKSHU}).",
        "Helps get the scammer's SIM and WhatsApp blocked so others are not targeted.")
    if money_lost:
        add(f"If your bank does not resolve the complaint within 30 days, escalate to the RBI Ombudsman ({RBI_CMS}).",
            "Free for customers; covers unauthorised electronic transactions.")
    add("Warn family and friends — scammers often reuse the same script on your contacts.",
        "Especially if your WhatsApp or e-mail was accessed.")

    if hours_since is not None and money_lost:
        if hours_since <= 2:
            steps[0]["why"] += " You are inside the golden hour — call before doing anything else."
        elif hours_since > 72:
            steps[0]["why"] += " Even after several days, report it: refunds and recoveries still happen."
    return steps


@dataclass
class IncidentDetails:
    name: str = ""
    phone: str = ""
    scam_type: str = "other"
    date_time: str = ""
    amount_lost: float = 0.0
    your_bank: str = ""
    transactions: list[dict] = field(default_factory=list)   # {utr, amount, to_upi_or_account, time}
    scammer_contacts: list[str] = field(default_factory=list)  # phone numbers, UPI IDs, websites, social handles
    description: str = ""


def complaint_draft(d: IncidentDetails) -> str:
    """Plain-text complaint the user can paste into cybercrime.gov.in."""
    lines = [
        "To: National Cyber Crime Reporting Portal / Cyber Crime Cell",
        "Subject: Complaint regarding online financial fraud"
        + (f" of ₹{d.amount_lost:,.0f}" if d.amount_lost else ""),
        "",
        f"I, {d.name or '[your full name]'}, mobile {d.phone or '[your mobile number]'}, "
        f"wish to report an online fraud ({SCAM_TYPES.get(d.scam_type, 'other').lower()}).",
        "",
        f"Date and time of incident: {d.date_time or '[date, time]'}",
        f"My bank / account: {d.your_bank or '[bank name, last 4 digits of account]'}",
    ]
    if d.amount_lost:
        lines.append(f"Total amount lost: ₹{d.amount_lost:,.2f}")
    lines += ["", "What happened:", (d.description.strip() or "[describe in your own words, in order of events]")]
    if d.transactions:
        lines += ["", "Transaction details:"]
        for i, t in enumerate(d.transactions, 1):
            amt = t.get("amount")
            amount_text = f"₹{float(amt):,.2f}" if amt not in (None, "") else "[amount]"
            lines.append(
                f"  {i}. UTR/Ref: {t.get('utr') or '[UTR]'} | Amount: {amount_text} | "
                f"Sent to: {t.get('to_upi_or_account') or '[UPI ID / account]'} | Time: {t.get('time') or '[time]'}"
            )
    if d.scammer_contacts:
        lines += ["", "Fraudster's details (numbers / UPI IDs / links / profiles):"]
        lines += [f"  - {c}" for c in d.scammer_contacts]
    lines += [
        "",
        "I request you to register my complaint, trace and freeze the amount in the receiving account(s), "
        "and take necessary action. I have informed my bank and saved screenshots of the messages and "
        "transaction SMS as evidence.",
        "",
        f"{d.name or '[name]'}",
        f"{d.phone or '[mobile]'}",
    ]
    return "\n".join(lines)
