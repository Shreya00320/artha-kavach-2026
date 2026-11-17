"""app/chat_ui.py – Ask Artha: chat about your own money, grounded in engine numbers."""

import streamlit as st

from app.budget_ui import get_budget_state


def render_chat_tab(adapter=None) -> None:
    from core.assistant import SUGGESTED_QUESTIONS, answer_question

    st.markdown("## 💬 Ask Artha")
    summary, txns, subs = get_budget_state()
    if summary is None:
        st.info("Load your SMS (or the sample data) in 💰 Smart Budget, then ask questions about your money here.")
        return

    st.caption(
        "Answers use only numbers computed from your transactions. "
        + ("An AI phrases the reply, and any reply with a number we didn't compute is replaced." if adapter
           else "Running offline — answers come from the rules engine.")
    )

    history = st.session_state.setdefault("chat_history", [])

    cols = st.columns(3)
    clicked = None
    for i, q in enumerate(SUGGESTED_QUESTIONS):
        if cols[i % 3].button(q, key=f"chat_suggest_{i}", width="stretch"):
            clicked = q

    for msg in history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("caption"):
                st.caption(msg["caption"])

    question = st.chat_input("Ask about your spending, savings, subscriptions…", key="chat_input") or clicked
    if question:
        history.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)
        ans = answer_question(question, summary, txns, adapter=adapter, subscriptions=subs)
        cap = "🤖 AI-phrased, numbers verified" if ans.method == "llm" else "📏 computed by rules"
        history.append({"role": "assistant", "content": ans.text, "caption": cap})
        with st.chat_message("assistant"):
            st.markdown(ans.text)
            st.caption(cap)

    if history and st.button("Clear chat", key="chat_clear"):
        st.session_state["chat_history"] = []
        st.rerun()
