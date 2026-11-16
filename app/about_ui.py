"""app/about_ui.py – About / How it Works tab for Artha Kavach."""

import streamlit as st

ARCHITECTURE_DIAGRAM = """
```
User input (SMS / CSV)
        │
        ▼
┌───────────────────────────────────────────┐
│              Artha Kavach                 │
│                                           │
│  ┌─────────────┐   ┌────────────────────┐ │
│  │ Scam Shield │   │   Smart Budget     │ │
│  │             │   │                    │ │
│  │ 1. Rules    │   │ 1. Parser (regex   │ │
│  │    engine   │   │    + LLM fallback) │ │
│  │ 2. ML (TF-  │   │ 2. Categoriser     │ │
│  │    IDF+LR)  │   │    (lookup + LLM)  │ │
│  │ 3. LLM judge│   │ 3. Budget engine   │ │
│  │ 4. Claim    │   │    (pure Python)   │ │
│  │    verifier │   │ 4. Nudge writer    │ │
│  └──────┬──────┘   └────────┬───────────┘ │
│         │                   │             │
│         └─────────┬─────────┘             │
│                   ▼                       │
│            Trust Receipt                  │
│  (sources · verified claims · detector    │
│   votes · code-computed values)           │
└───────────────────────────────────────────┘
        │
        ▼
  Verdict + Explanation + Evidence
```
"""


def render_about_tab() -> None:
    st.markdown("## 📖 About Artha Kavach")
    st.markdown(
        "> **\"An AI money coach that protects you from UPI scams, builds your budget "
        "from bank SMS, and never says anything it can't prove.\"**"
    )

    st.divider()

    # --- Why ---
    st.markdown("### 🎯 Why we built this")
    st.markdown(
        """
Finance apps fail because users cannot tell **when the AI is wrong**.

Artha Kavach solves this with a **Trust Receipt** — every AI explanation shows:
- 🔍 The **sources** it used
- ✅ **Verified** vs ❌ **unverified** claims
- 📏 **Code-computed numbers** (arithmetic done by Python, not the LLM)
- 🗳️ Which **detectors agreed** (rules · ML · LLM judge)

Target users: **students and first-job earners in India** using UPI, bank SMS, and digital payments.
        """
    )

    st.divider()

    # --- Design principle ---
    st.markdown("### 🏗️ Design principle")
    st.info(
        "**Use plain code** where code is reliable (arithmetic, parsing standard formats).  \n"
        "Use a **small classical model** for cheap, fast verdicts.  \n"
        "Use the **LLM only** where language understanding is needed — messy or Hinglish text, "
        "plain-language explanation, claim verification."
    )

    # Architecture diagram
    st.markdown("### 🗺️ Architecture")
    st.markdown(ARCHITECTURE_DIAGRAM)

    st.divider()

    # --- Scam Shield explained ---
    st.markdown("### 🛡️ How Scam Shield works")
    steps = [
        ("1. Rules engine",
         "Regex + keyword checks for OTP requests, collect-request scams, urgency language, "
         "phishing links, KYC threats, lottery/prize, job-fee scams. Fast and fully offline."),
        ("2. ML Classifier",
         "TF-IDF vectoriser + Logistic Regression trained on ~150 labelled messages (English, "
         "Hindi, Hinglish). Returns a 3-class probability: scam / suspicious / safe."),
        ("3. LLM Judge",
         "Receives the message, rule hits, classifier probability, and top-3 KB advisory passages. "
         "Returns strict JSON: verdict, confidence, red flags with exact quoted text, and verifiable claims."),
        ("4. Claim Verifier",
         "A second LLM call checks each claim against the cited KB passage. "
         "Unsupported claims are dropped or flagged — the LLM cannot bluff its sources."),
        ("5. Trust Receipt",
         "Assembles sources, verified claims, and all detector votes into a transparent panel "
         "shown below every verdict."),
    ]
    for title, body in steps:
        with st.expander(title):
            st.markdown(body)

    st.divider()

    # --- Smart Budget explained ---
    st.markdown("### 💰 How Smart Budget works")
    b_steps = [
        ("1. Hybrid SMS parser",
         "Regex templates for SBI, HDFC, ICICI, Axis, Kotak, UPI/PhonePe/GPay formats. "
         "LLM fallback (with JSON-schema output) for messages the regex cannot parse. "
         "Every message is logged as 'regex' | 'llm' | 'failed'."),
        ("2. Categoriser",
         "Merchant lookup table first (Swiggy, Zomato, Uber, Amazon, rent, etc.). "
         "LLM fallback for unknown merchants; results cached to avoid re-calling."),
        ("3. Budget engine (pure Python)",
         "Monthly totals by category, 50/30/20 comparison, savings rate, recurring-payment detection, "
         "and pace projection. All arithmetic is code — zero LLM involvement."),
        ("4. Nudge writer",
         "The LLM receives ONLY code-computed numbers and writes 2–3 short, kind nudges. "
         "A post-check rejects any nudge that contains a number not present in the engine output."),
        ("5. Step-up savings chart",
         "Pure-code function compares a flat-savings plan vs Save More Tomorrow (SMarT). "
         "Clearly labelled as an illustration — not a financial guarantee."),
    ]
    for title, body in b_steps:
        with st.expander(title):
            st.markdown(body)

    st.divider()

    # --- Trust Receipt explained ---
    st.markdown("### 🔍 The Trust Receipt")
    st.markdown(
        """
Every AI output in Artha Kavach carries a **Trust Receipt** — a collapsible panel that shows exactly:

| Field | What it means |
|---|---|
| **Sources** | KB document title, publisher, URL — what the AI actually read |
| **Verified claims** | Each claim cross-checked against its cited passage by a second LLM call |
| **Code-computed values** | Budget numbers with their formula and inputs — Python arithmetic, not LLM estimation |
| **Detector votes** | Rules engine · ML classifier · LLM judge — which agreed, which didn't |
| **Confidence note** | Plain-English explanation of how certain the system is |
        """
    )

    st.divider()

    # --- Knowledge base ---
    st.markdown("### 📚 Knowledge base")
    st.markdown(
        """
The RAG knowledge base (`data/kb/`) contains advisory documents from:
- **RBI** — UPI safety guidelines, OTP/PIN warnings
- **NPCI** — Collect-request awareness
- **MeitY / Cyber Dost** — Phishing, KYC fraud, job-scam warnings
- **cybercrime.gov.in** — How to report
- **Financial literacy portals** — Budgeting and savings guidance

All documents are real public sources. See `data/kb/TODO_manual_verification.md` for the full list.
        """
    )

    st.divider()

    # --- Limitations ---
    st.markdown("### ⚠️ Limitations & honest caveats")
    st.warning(
        """
- **Scam detection is not perfect.** New scam patterns not covered by rules or training data may be missed.
- **Classifier trained on synthetic data.** Real-world performance may differ; treat confidence scores as indicative.
- **Parser covers common formats.** Unusual or bank-specific SMS formats may fall through to LLM or fail entirely.
- **LLM calls cost money and have latency.** The app degrades gracefully to rules-only when no API key is set.
- **Not a substitute for professional advice.** Always verify with your bank or the [cybercrime.gov.in](https://cybercrime.gov.in) portal.
        """
    )

    # --- Dataset note ---
    st.markdown("### 📊 Datasets")
    st.markdown(
        """
| File | Description |
|---|---|
| `data/scam_eval.csv` | ~150 labelled messages (synthetic, English/Hindi/Hinglish). 70/30 train/test split, seed=42. |
| `data/sample_sms.csv` | ~120 synthetic bank/UPI SMS across one month. Marked **SYNTHETIC** in README. |
        """
    )

    st.divider()

    # --- About hackathon ---
    st.markdown("### 🏆 Arthaton 2026")
    st.markdown(
        "Built for **Arthaton 2026** — *\"AI for Finance\"* hackathon. Theme: AI tools for Indian users "
        "(UPI, bank SMS, NSE, tax, scams, small business). Submission deadline: 22 Nov 2026."
    )

    st.caption(
        "⚖️ **Disclaimer:** Artha Kavach is an educational tool. "
        "It does not give financial, legal, or investment advice. "
        "Always verify with your bank or the official cybercrime.gov.in portal. "
        "All datasets are synthetic and for demonstration purposes only."
    )
