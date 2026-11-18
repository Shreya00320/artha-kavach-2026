"""app/chat_ui.py – Ask Artha: a money coach you can chat with.

Works with or without the user's bank data:
  - general money questions (SIP, tax, credit score, insurance…) are answered from the knowledge base;
  - questions about *their own* spending use numbers computed from their transactions;
  - scam-looking text, stock-tip requests and prompt-injection attempts get safe, fixed responses.
"""

import streamlit as st

from app.budget_ui import get_budget_state


def _caption(reply) -> str:
    bits = []
    if reply.intent == "personal":
        bits.append("📏 computed from your transactions")
    elif reply.method == "llm":
        bits.append("🤖 AI-phrased from vetted sources, numbers verified")
    elif reply.intent in ("refuse_advice", "refuse_injection", "warn_returns", "scam", "safety"):
        bits.append("🛡️ safety guard")
    elif reply.intent == "knowledge":
        bits.append("📚 from the Artha knowledge base")
    if reply.sources and reply.intent != "personal":
        bits.append("Sources: " + "; ".join(f"{title.split(' — ')[0]} ({sid})" for sid, title in reply.sources[:2]))
    return " · ".join(bits)


def render_chat_tab(adapter=None) -> None:
    from core.advisor import STARTER_QUESTIONS, respond
    from core.assistant import SUGGESTED_QUESTIONS

    st.markdown("## 💬 Ask Artha")
    summary, txns, subs = get_budget_state()

    st.caption(
        "Your friendly money coach: ask about saving, investing basics, tax, credit scores, loans, insurance "
        "or scams"
        + (", or about your own spending." if summary is not None
           else ". Load your SMS in 💰 Smart Budget to also ask about your own spending.")
        + " I explain and educate — I don't pick stocks or promise returns. "
        + ("An AI phrases replies from vetted sources and any unbacked number is rejected."
           if adapter else "Running offline — answers come from the knowledge base and rules engine.")
    )

    history = st.session_state.setdefault("chat_history", [])

    suggestions = (SUGGESTED_QUESTIONS[:3] + STARTER_QUESTIONS[:3]) if summary is not None else STARTER_QUESTIONS
    cols = st.columns(3)
    clicked = None
    for i, q in enumerate(suggestions):
        if cols[i % 3].button(q, key=f"chat_suggest_{i}", width="stretch"):
            clicked = q

    for msg in history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("caption"):
                st.caption(msg["caption"])

    question = st.chat_input("Ask Artha anything about money…", key="chat_input") or clicked
    if question:
        prior = [{"role": m["role"], "content": m["content"]} for m in history]
        history.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)
        reply = respond(question, history=prior, summary=summary, txns=txns,
                        subscriptions=subs, adapter=adapter)
        cap = _caption(reply)
        history.append({"role": "assistant", "content": reply.text, "caption": cap})
        with st.chat_message("assistant"):
            st.markdown(reply.text)
            if cap:
                st.caption(cap)

    if history and st.button("Clear chat", key="chat_clear"):
        st.session_state["chat_history"] = []
        st.rerun()
