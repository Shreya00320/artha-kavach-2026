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
    st.markdown(
        """
**One app, six jobs:**

| Tab | What you can do |
|---|---|
| 🛡️ **Scam Shield** | Check a message · check a link (never opened) · scan a whole inbox · 🆘 "I've been scammed" plan + complaint draft |
| 💰 **Smart Budget** | Budget from bank SMS · transfers & refunds handled · salary-cycle months · subscriptions · unusual-payment alerts · fix categories · CSV export |
| 🎯 **Goals & Planner** | Emergency fund · multi-goal plan · SIP & EMI calculators · loan prepayment · step-up saving |
| 🧾 **Tax** | Old vs new regime (FY 2026-27) with deductions pre-filled from your payments |
| 💬 **Ask Artha** | Chat about your money — every number in a reply is checked against the engine |
| 📖 **About** | How it works, sources and limits |
        """
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
         "50+ regex/keyword checks for OTP/PIN requests, collect-request scams, urgency language, "
         "phishing links, KYC threats, lottery/prize, job-fee scams, 'digital arrest', parcel/courier "
         "threats, APK installs, QR-to-receive, task/trading-group scams and Hinglish variants. "
         "Fast and fully offline."),
        ("2. ML Classifier",
         "TF-IDF (word 1-2 grams + character 2-5 grams, which handle Hinglish spellings) + Logistic "
         "Regression trained on ~108 labelled messages. Returns scam / suspicious / safe probabilities. "
         "Offline, the more severe of the rules and classifier verdicts wins."),
        ("3. LLM Judge",
         "Receives the message, rule hits, classifier probability, and top-3 KB advisory passages. "
         "Returns strict JSON: verdict, confidence, red flags with exact quoted text, and verifiable claims."),
        ("4. Claim Verifier",
         "A second LLM call checks each claim against the cited KB passage. "
         "Unsupported claims are dropped or flagged — the LLM cannot bluff its sources."),
        ("5. Link checker",
         "Every URL in the message is inspected offline (never opened): official bank/government "
         "domains, look-alike and misspelled domains, shorteners, raw IPs, punycode, risky TLDs, .apk downloads."),
        ("6. Trust Receipt",
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
         "Regex templates for SBI, HDFC, ICICI, Axis, Kotak, UPI/PhonePe/GPay/Paytm formats plus "
         "generic bank templates and several date formats. "
         "LLM fallback (with JSON-schema output) for messages the regex cannot parse. "
         "Every message is logged as 'regex' | 'llm' | 'failed'."),
        ("2. Categoriser",
         "Merchant lookup (whole-word matching, 200+ merchants), brand names recovered from UPI IDs, "
         "person-to-person UPI detected as transfers, refunds detected. LLM fallback for unknown "
         "merchants. You can correct any category and the budget recomputes."),
        ("3. Budget engine (pure Python)",
         "Monthly totals by category, 50/30/20 comparison, savings rate, recurring-payment detection, "
         "pace projection, subscriptions, unusual-payment alerts, small-spend bucket and salary-cycle "
         "months. Transfers to people are kept out of spending; refunds are netted off. "
         "All arithmetic is code — zero LLM involvement."),
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
- **cybercrime.gov.in / I4C** — How to report; 'digital arrest', task and investment scams
- **RBI 2017 circular** — zero liability for unauthorised electronic transactions reported quickly
- **DoT Sanchar Saathi (Chakshu)** — reporting fraud calls and messages
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
- **Tax and planning tools are estimates.** Tax uses FY 2026-27 slabs for salaried people under 60 and skips surcharge and capital gains; returns in calculators are assumptions, not predictions.
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
| `data/scam_eval.csv` | 155 labelled messages (synthetic, English/Hindi/Hinglish). 70/30 train/test split, seed=42. |
| `data/sample_sms.csv` | 96 synthetic bank/UPI SMS across two months. Marked **SYNTHETIC** in README. |
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
