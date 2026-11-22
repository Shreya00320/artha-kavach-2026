"""app/scam_ui.py – Scam Shield tab for Artha Kavach.

Sub-tabs:
  🔍 Check a message   – full pipeline (rules → ML → RAG → LLM judge → verifier) + link report
  🔗 Check a link      – offline URL inspection (never opens the link)
  📥 Scan many messages – paste a whole inbox, get a triaged list
  🆘 I've been scammed – golden-hour action plan + complaint draft

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
from app.styles import VERDICT_EMOJI

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
    "🚨 'Digital arrest' threat": (
        "This is Mumbai Cyber Police. A FedEx parcel booked on your Aadhaar contains drugs. "
        "Join the video call now for your statement or you will be under digital arrest."
    ),
    "🚨 Task / trading-group scam": (
        "Part time job! Like YouTube videos and earn Rs 150 per task. "
        "Join our VIP stock tips group on Telegram for guaranteed returns of 30% every month."
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
    "🧠 Needs AI: 'papa' on a new number (Hinglish)": (
        "Beta papa bol raha hu, purana phone kharab ho gaya. Ye naya number save kar lo. "
        "Hospital mein ek dost ke liye 18000 chahiye, abhi is UPI pe bhej do, ghar aake samjhata hu."
    ),
    "🧠 Needs AI: polite 'HR' message, no trigger words": (
        "Hello! Your profile was shortlisted by our hiring team for a remote Amazon support role. "
        "Please message our recruiter on WhatsApp to complete onboarding and confirm your slot today."
    ),
    "🧠 Needs AI: fake electricity officer": (
        "Dear consumer, your previous month bill update is not reflected in our system. "
        "Kindly contact our officer Mr. Sharma on 9123456780 tonight to avoid inconvenience."
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

LINK_ICON = {"safe": "✅", "caution": "⚠️", "danger": "🚨"}


# ---------------------------------------------------------------------------
# Shared renderers
# ---------------------------------------------------------------------------

def render_link_reports(reports, heading: str = "🔗 Links in this message") -> None:
    if not reports:
        return
    st.markdown(f"**{heading}**")
    for r in reports:
        org = f" · official **{r.official_org}**" if r.official_org else ""
        st.markdown(f"{LINK_ICON[r.verdict]} `{r.url}` — **{r.verdict.upper()}**{org}")
        for why in r.reasons:
            st.caption(f"• {why}")


def _render_detector_strip(result) -> None:
    """Show how each detector voted, so the AI's contribution is visible."""
    score = result.rule_result.score
    rules_v = "scam" if score >= 0.55 else "suspicious" if score >= 0.25 else "safe"
    votes = [("📏 Rules", rules_v, f"{score * 100:.0f}% score")]
    if result.classifier_proba:
        clf_v = max(result.classifier_proba, key=result.classifier_proba.get)
        votes.append(("🧠 Deep model", clf_v, f"{result.classifier_proba[clf_v] * 100:.0f}% sure"))
    final_label = "🧠 AI judge (final)" if result.llm_used else "⚖️ Combined (final)"
    votes.append((final_label, result.verdict, f"{result.confidence * 100:.0f}% confidence"))
    for col, (name, v, detail) in zip(st.columns(len(votes)), votes):
        col.metric(name, f"{VERDICT_EMOJI.get(v, '')} {v}", detail, delta_color="off")
    if result.llm_used and result.verdict != rules_v:
        st.info(f"🧠 **The AI judge changed the verdict:** the rules alone said *{rules_v}*, "
                f"but reading the whole message the AI judged it *{result.verdict}*. "
                "Its reasons are quoted below and checked in the Trust Receipt.")
    elif not result.llm_used and rules_v == "safe" and result.verdict != "safe":
        st.info("🤖 No rule fired, but the deep model recognised the pattern from training examples.")


# ---------------------------------------------------------------------------
# Sub-tab: check one message
# ---------------------------------------------------------------------------

def _clear_scam_check() -> None:
    """on_click callback: wipe the textarea and cached result BEFORE next render.

    Using a callback avoids StreamlitWidgetAlreadyInstantiatedError that occurs
    when session_state is written to a widget key *after* that widget has
    already been rendered in the same script run.
    """
    st.session_state["scam_textarea"] = ""
    st.session_state.pop("scam_result", None)


def _load_sample_scam(label: str) -> None:
    """on_click callback: load a sample message BEFORE next render."""
    st.session_state["scam_textarea"] = SAMPLE_MESSAGES[label]
    st.session_state.pop("scam_result", None)


def _render_check_message(adapter, retriever, classifier) -> None:
    st.markdown(
        "Paste any suspicious SMS, WhatsApp message, or UPI collect-request "
        "description. Works in **English, Hindi, and Hinglish**."
    )

    with st.expander("📋 Load a sample message"):
        chosen_label = st.selectbox(
            "Pick a sample", list(SAMPLE_MESSAGES.keys()), label_visibility="collapsed"
        )
        # Use on_click so the state write happens before text_area is rendered
        st.button(
            "Load sample",
            key="load_sample_scam",
            on_click=_load_sample_scam,
            args=(chosen_label,),
        )

    message = st.text_area(
        "Message to analyse",
        height=130,
        placeholder="Paste SMS / WhatsApp / UPI collect-request text here…",
        key="scam_textarea",
    )

    col_btn, col_clear = st.columns([3, 1])
    with col_btn:
        analyse_clicked = st.button("🔍 Analyse message", type="primary", width="stretch")
    with col_clear:
        # on_click runs BEFORE rerender — no WidgetAlreadyInstantiatedError
        st.button("Clear", on_click=_clear_scam_check, width="stretch")

    if analyse_clicked and message.strip():
        with st.spinner("Analysing…"):
            from scam.pipeline import analyse
            result = analyse(message.strip(), adapter=adapter, retriever=retriever, classifier=classifier)
        st.session_state["scam_result"] = result
    elif analyse_clicked:
        st.warning("Please paste a message first.")

    result = st.session_state.get("scam_result")
    if result is None:
        return

    st.divider()
    render_verdict_badge(result.verdict, result.confidence)

    modes = []
    if result.llm_used:
        modes.append("LLM judge")
    if result.classifier_used:
        modes.append("ML classifier")
    if result.retriever_used:
        modes.append("KB retrieval")
    modes.append("Rules engine")
    st.caption(f"⚡ Analysed in {result.elapsed_ms:.0f} ms  ·  Pipeline: {', '.join(modes)}")
    _render_detector_strip(result)

    if result.verdict == "scam":
        st.error(
            "**Already paid or shared an OTP/PIN?** Call **1930** now and open the "
            "**🆘 I've been scammed** tab for a step-by-step plan."
        )

    st.divider()
    left, right = st.columns([3, 2])
    with left:
        from scam.tactics import tactics_for
        _tac = tactics_for(result.rule_result)
        if _tac:
            st.markdown("**🧠 Manipulation tactics used**")
            for _t in _tac:
                st.markdown(f"- **{_t['tactic']}** — {_t['why']}  \n  🛡️ *{_t['defence']}*")
        render_red_flags(result.message, result.red_flags)
        from scam.link_check import check_text
        render_link_reports(check_text(result.message))
    with right:
        render_what_to_do(result.what_to_do)

        with st.expander(f"📏 Rules engine — {result.rule_result.n_rules_matched} rule(s) matched"):
            if result.rule_result.matches:
                for m in result.rule_result.matches:
                    st.markdown(
                        f"- **{m.rule_id}** `{m.category}` (weight {m.weight:.2f}) — *{m.name}*  \n"
                        f"  Matched: `{m.matched_text}`"
                    )
            else:
                st.info("No rules matched.")
            st.caption(f"Composite score: **{result.rule_result.score:.3f}**")

        if result.classifier_proba:
            with st.expander("🧠 Deep model probabilities"):
                for label, prob in sorted(result.classifier_proba.items(), key=lambda x: -x[1]):
                    st.progress(min(max(prob, 0.0), 1.0), text=f"{label}: {prob * 100:.1f}%")

    st.divider()
    render_trust_receipt(result.trust_receipt)

    if not result.llm_used:
        st.info(
            "ℹ️ **Offline mode** — LLM judge is not available. Verdict is based on rules engine"
            + (" + ML classifier" if result.classifier_used else "")
            + " only. Accuracy may be lower."
        )


# ---------------------------------------------------------------------------
# Sub-tab: check a link
# ---------------------------------------------------------------------------

def _render_check_link() -> None:
    st.markdown(
        "Paste a link from an SMS, e-mail or WhatsApp. Artha Kavach **never opens the link** — "
        "it only inspects the address for phishing patterns."
    )
    link_text = st.text_area(
        "Link(s) or message containing links",
        key="link_input",
        height=90,
        placeholder="e.g. http://sbi-kyc-update.xyz/login  or  bit.ly/3abcd",
    )
    if st.button("🔗 Check link", type="primary", key="btn_link"):
        from scam.link_check import check_text, check_url
        reports = check_text(link_text)
        if not reports and link_text.strip():
            reports = [check_url(link_text.strip().split()[0])]
        if not reports:
            st.warning("Paste at least one link.")
        else:
            worst = max(reports, key=lambda r: {"safe": 0, "caution": 1, "danger": 2}[r.verdict])
            {"danger": st.error, "caution": st.warning, "safe": st.success}[worst.verdict](
                {"danger": "🚨 Do not open — this looks like a phishing link.",
                 "caution": "⚠️ Be careful — some warning signs.",
                 "safe": "✅ Official domain. Still: never share OTP/PIN on any site you reached from a message."}[worst.verdict]
            )
            render_link_reports(reports, heading="Results")
    st.caption(
        "Tip: type your bank's address yourself, or use the official app, instead of tapping links in messages."
    )


# ---------------------------------------------------------------------------
# Sub-tab: scan many messages
# ---------------------------------------------------------------------------

def _render_bulk_scan(classifier) -> None:
    st.markdown(
        "Paste many messages at once (**one per line**) — e.g. copy your SMS inbox. "
        "Each is checked offline with the rules engine, ML classifier and link checker, "
        "so this works without an API key and nothing leaves your session."
    )
    bulk = st.text_area("Messages, one per line", key="bulk_input", height=200)
    if st.button("📥 Scan all", type="primary", key="btn_bulk"):
        lines = [l.strip() for l in bulk.splitlines() if l.strip()]
        if not lines:
            st.warning("Paste at least one message.")
            return
        if len(lines) > 500:
            st.info("Scanning the first 500 messages.")
            lines = lines[:500]
        from scam.pipeline import analyse
        from scam.link_check import check_text
        rows = []
        with st.spinner(f"Scanning {len(lines)} messages…"):
            for line in lines:
                r = analyse(line, adapter=None, retriever=None, classifier=classifier)
                links = check_text(line)
                link_flag = max((l.verdict for l in links), key=lambda v: {"safe": 0, "caution": 1, "danger": 2}[v], default="")
                rows.append({
                    "Verdict": f"{VERDICT_EMOJI.get(r.verdict, '')} {r.verdict}",
                    "Confidence": f"{r.confidence * 100:.0f}%",
                    "Top red flag": r.red_flags[0].flag if r.red_flags else "",
                    "Link": f"{LINK_ICON.get(link_flag, '')} {link_flag}".strip(),
                    "Message": line[:160],
                    "_sev": {"scam": 0, "suspicious": 1, "safe": 2}[r.verdict],
                })
        rows.sort(key=lambda x: x["_sev"])
        n_scam = sum(r["_sev"] == 0 for r in rows)
        n_susp = sum(r["_sev"] == 1 for r in rows)
        c1, c2, c3 = st.columns(3)
        c1.metric("🚨 Scam", n_scam)
        c2.metric("⚠️ Suspicious", n_susp)
        c3.metric("✅ Looks safe", len(rows) - n_scam - n_susp)
        st.dataframe([{k: v for k, v in r.items() if k != "_sev"} for r in rows],
                     hide_index=True, width="stretch")
        st.caption("Open a message in 🔍 Check a message for the full explanation and Trust Receipt.")


# ---------------------------------------------------------------------------
# Sub-tab: I've been scammed
# ---------------------------------------------------------------------------

def _render_emergency() -> None:
    from scam.emergency import SCAM_TYPES, action_plan, complaint_draft, IncidentDetails, HELPLINE, PORTAL

    st.error(
        f"### 📞 Lost money? Call **{HELPLINE}** now\n"
        f"National Cyber Crime Helpline — the sooner you report, the better the chance the money "
        f"can be frozen. You can also file at **{PORTAL}**."
    )

    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        scam_type = st.selectbox("What happened?", list(SCAM_TYPES), format_func=SCAM_TYPES.get, key="em_type")
    with c2:
        money_lost = st.radio("Money lost?", ["Yes", "No"], horizontal=True, key="em_lost") == "Yes"
    with c3:
        hours = st.number_input("Hours since it happened", min_value=0.0, value=1.0, step=1.0, key="em_hours")

    st.markdown("#### ✅ Your action plan")
    for i, s in enumerate(action_plan(scam_type, money_lost, hours), 1):
        prefix = "🔴 " if s["urgent"] else ""
        st.checkbox(f"{prefix}**{i}. {s['step']}**", key=f"em_step_{scam_type}_{i}", help=s["why"])
        st.caption(s["why"])

    st.markdown("#### 📝 Complaint draft for cybercrime.gov.in")
    st.caption("Fill what you know — the rest stays as [placeholders]. Nothing is sent anywhere.")
    with st.form("complaint_form"):
        a, b = st.columns(2)
        name = a.text_input("Your name")
        phone = b.text_input("Your mobile number")
        when = a.text_input("Date & time of incident", placeholder="17-Nov-2026, 3:40 pm")
        bank = b.text_input("Your bank & account (last 4 digits)", placeholder="SBI XX4521")
        amount = a.number_input("Total amount lost (₹)", min_value=0.0, step=100.0)
        utr = b.text_input("Transaction ref / UTR (comma-separate several)")
        to = a.text_input("Money sent to (UPI ID / account)")
        contacts = b.text_input("Scammer's numbers / links / profiles (comma-separated)")
        desc = st.text_area("What happened, in your words", height=100)
        submitted = st.form_submit_button("Generate complaint text")
    if submitted:
        utrs = [u.strip() for u in utr.split(",") if u.strip()]
        txns = [{"utr": u, "amount": amount if len(utrs) == 1 else None, "to_upi_or_account": to} for u in utrs]
        if not txns and (amount or to):
            txns = [{"utr": "", "amount": amount or None, "to_upi_or_account": to}]
        text = complaint_draft(IncidentDetails(
            name=name, phone=phone, scam_type=scam_type, date_time=when, amount_lost=amount,
            your_bank=bank, transactions=txns,
            scammer_contacts=[c.strip() for c in contacts.split(",") if c.strip()], description=desc,
        ))
        st.code(text, language=None)
        st.download_button("⬇️ Download as .txt", text, file_name="cybercrime_complaint.txt")


# ---------------------------------------------------------------------------
# Main tab renderer
# ---------------------------------------------------------------------------

def render_scam_tab(adapter=None, retriever=None, classifier=None) -> None:
    st.markdown("## 🛡️ Scam Shield")
    t_msg, t_link, t_bulk, t_sos = st.tabs(
        ["🔍 Check a message", "🔗 Check a link", "📥 Scan many messages", "🆘 I've been scammed"]
    )
    with t_msg:
        _render_check_message(adapter, retriever, classifier)
    with t_link:
        _render_check_link()
    with t_bulk:
        _render_bulk_scan(classifier)
    with t_sos:
        _render_emergency()
