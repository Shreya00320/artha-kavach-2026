"""app/scam_ui.py – Scam Shield tab for Artha Kavach.

Provides:
  render_scam_tab(adapter, retriever, classifier) -> None
"""

import streamlit as st

from app.components import (
    render_verdict_badge,
    render_red_flags,
    render_what_to_do,
    render_trust_receipt,
)

# ---------------------------------------------------------------------------
# Sample scam messages (one-click demo)
# ---------------------------------------------------------------------------

SAMPLE_MESSAGES = {
    "🚨 UPI collect-request scam": (
        "Rs 1 collect request sent to verify your Paytm account. "
        "Accept to receive Rs 10,000 cashback refund. "
        "Offer expires in 10 minutes. Act NOW!"
    ),
    "🚨 OTP phishing (Hinglish)": (
        "Aapka SBI account block ho jayega. "
        "Abhi apna OTP 7382 share karo ya yahan click karo: "
        "http://sbi-kyc.update.click/verify"
    ),
    "🚨 Fake job offer": (
        "Congratulations! Work from home opportunity. "
        "Earn Rs 15,000/day. Pay Rs 999 registration fee to unlock tasks. "
        "WhatsApp: 9876543210"
    ),
    "⚠️ Suspicious prize claim": (
        "Dear Customer, You have won Rs 5,00,000 in NPCI lucky draw. "
        "Pay processing fee Rs 500 to claim. Call 9999988888."
    ),
    "✅ Legitimate bank debit": (
        "Rs 1,250.00 debited from A/c XX4521 on 14-Nov-26 at SWIGGY. "
        "Avl Bal: Rs 12,340.50 —SBI"
    ),
    "✅ UPI credit (legitimate)": (
        "Rs 5,000.00 credited to your A/c XX7823 on 01-Nov-26 "
        "(NEFT from RAHUL SHARMA). Avl Bal: Rs 23,450.00 —HDFC"
    ),
}


# ---------------------------------------------------------------------------
# Main tab renderer
# ---------------------------------------------------------------------------

def render_scam_tab(adapter=None, retriever=None, classifier=None) -> None:
    st.markdown("## 🛡️ Scam Shield")
    st.markdown(
        "Paste any suspicious SMS, WhatsApp message, or UPI collect-request "
        "description below. Works in **English, Hindi, and Hinglish**."
    )

    # ---- One-click sample data ----
    with st.expander("📋 Load a sample message"):
        chosen_label = st.selectbox(
            "Pick a sample", list(SAMPLE_MESSAGES.keys()), label_visibility="collapsed"
        )
        if st.button("Load sample", key="load_sample_scam"):
            st.session_state["scam_input"] = SAMPLE_MESSAGES[chosen_label]

    # ---- Text input ----
    message = st.text_area(
        "Message to analyse",
        value=st.session_state.get("scam_input", ""),
        height=130,
        placeholder="Paste SMS / WhatsApp / UPI collect-request text here…",
        key="scam_textarea",
    )

    col_btn, col_clear = st.columns([3, 1])
    with col_btn:
        analyse_clicked = st.button(
            "🔍 Analyse message", type="primary", use_container_width=True
        )
    with col_clear:
        if st.button("Clear", use_container_width=True):
            st.session_state["scam_input"] = ""
            st.session_state.pop("scam_result", None)
            st.rerun()

    # ---- Run pipeline ----
    if analyse_clicked and message.strip():
        with st.spinner("Analysing…"):
            from scam.pipeline import analyse
            result = analyse(
                message.strip(),
                adapter=adapter,
                retriever=retriever,
                classifier=classifier,
            )
        st.session_state["scam_result"] = result

    elif analyse_clicked and not message.strip():
        st.warning("Please paste a message first.")

    # ---- Render results ----
    result = st.session_state.get("scam_result")
    if result is None:
        return

    st.divider()

    # Verdict badge
    render_verdict_badge(result.verdict, result.confidence)

    # Pipeline mode label
    modes = []
    if result.llm_used:
        modes.append("LLM judge")
    if result.classifier_used:
        modes.append("ML classifier")
    if result.retriever_used:
        modes.append("KB retrieval")
    modes.append("Rules engine")
    st.caption(
        f"⚡ Analysed in {result.elapsed_ms:.0f} ms  ·  "
        f"Pipeline: {', '.join(modes)}"
    )

    st.divider()

    # Red flags + actions side-by-side
    left, right = st.columns([3, 2])
    with left:
        render_red_flags(result.message, result.red_flags)
    with right:
        render_what_to_do(result.what_to_do)

        # Rules detail (always shown)
        with st.expander(
            f"📏 Rules engine — {result.rule_result.n_rules_matched} rule(s) matched"
        ):
            if result.rule_result.matches:
                for m in result.rule_result.matches:
                    st.markdown(
                        f"- **{m.rule_id}** `{m.category}` "
                        f"(weight {m.weight:.2f}) — *{m.description}*  \n"
                        f"  Matched: `{m.matched_text}`"
                    )
            else:
                st.info("No rules matched.")
            st.caption(
                f"Composite score: **{result.rule_result.score:.3f}**"
            )

        # Classifier detail (if run)
        if result.classifier_proba:
            proba = result.classifier_proba
            with st.expander("🤖 ML Classifier probabilities"):
                for label, prob in sorted(
                    proba.items(), key=lambda x: -x[1]
                ):
                    bar = "█" * int(prob * 20)
                    st.markdown(
                        f"`{label:>12}` {bar} **{prob*100:.1f}%**"
                    )

    st.divider()

    # Trust Receipt
    render_trust_receipt(result.trust_receipt)

    # Fallback / no-LLM notice
    if not result.llm_used:
        st.info(
            "ℹ️ **Offline mode** — LLM judge is not available. "
            "Verdict is based on rules engine"
            + (" + ML classifier" if result.classifier_used else "")
            + " only. Accuracy may be lower."
        )
