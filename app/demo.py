"""app/demo.py – One-click demo story for presentations.

Story: a student receives a 'digital arrest' message, has already paid ₹25,000,
and then checks the damage to their month.

  1. 🛡️ Scam Shield   → message is pre-filled; click Analyse → SCAM + 🆘 plan
  2. 💰 Smart Budget  → a month of SMS incl. the ₹25,000 UPI payment, flagged in 🔔 Alerts
  3. 💬 Ask Artha     → "Can I still afford rent?" / "Where can I cut back?"
"""

import csv

import streamlit as st

DEMO_SCAM_MESSAGE = (
    "This is Inspector Rathore, Mumbai Cyber Crime. A FedEx parcel booked on your Aadhaar "
    "contains MDMA drugs and fake passports. A money laundering case is filed. Join the video "
    "call now and stay on camera — you are under digital arrest. Transfer Rs 25,000 to "
    "cbi.verification.cell@ybl for fund verification, it will be refunded."
)

DEMO_FRAUD_SMS = [
    "Sent Rs 25,000.00 to cbi.verification.cell@ybl via UPI on 14-Nov-26. UPI Ref: 556677889900. —PhonePe",
]

DEMO_QUESTIONS = ["Can I afford ₹9,000 for rent?", "Where can I cut back?"]


def load_demo_story(sample_path: str = "data/sample_sms.csv") -> None:
    """Fill session state so every tab is ready for the walkthrough."""
    from app.budget_ui import _parse_and_categorise

    with open(sample_path, encoding="utf-8") as f:
        messages = [r["raw_sms"] for r in csv.DictReader(f) if r.get("raw_sms")]
    st.session_state["budget_txns_all"] = _parse_and_categorise(messages + DEMO_FRAUD_SMS)
    st.session_state["budget_overrides"] = {}
    st.session_state["scam_textarea"] = DEMO_SCAM_MESSAGE
    st.session_state.pop("scam_result", None)
    st.session_state["em_type"] = "digital_arrest"
    st.session_state["chat_history"] = []
