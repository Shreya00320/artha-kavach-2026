"""app/main.py – Artha Kavach Streamlit application.

Three-tab UI:
  1. Scam Shield  — detect UPI / bank fraud in SMS messages
  2. Smart Budget — categorise bank SMS, 50/30/20 budget, nudges, savings chart
  3. About        — architecture, design principles, limitations, disclaimer

Run:
  streamlit run app/main.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import logging
import os

import streamlit as st
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Page config — MUST be first Streamlit call
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Artha Kavach",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

load_dotenv()
logging.basicConfig(level=logging.INFO)

from app.styles import GLOBAL_CSS
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Initialise singletons (cached across reruns)
# ---------------------------------------------------------------------------

@st.cache_resource(show_spinner="Loading LLM adapter…")
def _get_adapter():
    """Return a live LLMAdapter, or None if no API key is set."""
    provider = os.getenv("LLM_PROVIDER", "gemini")
    api_key  = os.getenv("GEMINI_API_KEY", "") or os.getenv("LLM_API_KEY", "")
    if not api_key and provider == "gemini":
        return None
    try:
        from llm.adapter import LLMAdapter
        return LLMAdapter()
    except Exception as exc:
        logging.warning("LLM adapter init failed: %s", exc)
        return None


@st.cache_resource(show_spinner="Loading knowledge base…")
def _get_retriever():
    """Return a Retriever from the saved FAISS index, or None."""
    api_key = os.getenv("GEMINI_API_KEY", "") or os.getenv("LLM_API_KEY", "")
    if not api_key:
        return None
    try:
        from google import genai
        from rag.retrieve import build_retriever
        client = genai.Client(api_key=api_key)
        return build_retriever(".cache", client)
    except Exception as exc:
        logging.warning("Retriever init failed: %s", exc)
        return None


@st.cache_resource(show_spinner="Training classifier…")
def _get_classifier():
    """Return a trained ScamClassifier, or None."""
    try:
        from scam.classifier import ScamClassifier
        clf = ScamClassifier()
        clf.train("data/scam_eval.csv")
        return clf
    except Exception as exc:
        logging.warning("Classifier init failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

col_logo, col_title = st.columns([1, 10])
with col_logo:
    st.markdown("# 🛡️")
with col_title:
    st.markdown("# Artha Kavach")
    st.caption(
        "AI money coach for India · protects from UPI scams · builds your budget · "
        "never says anything it can't prove"
    )

st.divider()

# ---------------------------------------------------------------------------
# Status sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown("### ⚙️ System status")
    adapter    = _get_adapter()
    retriever  = _get_retriever()
    classifier = _get_classifier()

    st.markdown(
        f"{'✅' if adapter    else '⚠️'} **LLM** — "
        f"{'Live (Gemini)' if adapter else 'Offline (rules fallback)'}"
    )
    st.markdown(
        f"{'✅' if retriever  else '⚠️'} **Knowledge base** — "
        f"{'Loaded' if retriever else 'Not loaded (no embeddings)'}"
    )
    st.markdown(
        f"{'✅' if classifier else '⚠️'} **ML Classifier** — "
        f"{'Trained' if classifier else 'Not available'}"
    )

    if not adapter:
        st.info(
            "Set `LLM_API_KEY` (or `GEMINI_API_KEY`) in `.env` or Streamlit Secrets to enable the LLM judge.  \n"
            "The app works offline using rules + ML only."
        )

    st.divider()
    st.markdown("**Arthaton 2026** — AI for Finance")
    st.caption("⚖️ Educational tool. Not financial advice.")

# ---------------------------------------------------------------------------
# Main tabs
# ---------------------------------------------------------------------------

tab_scam, tab_budget, tab_about = st.tabs(
    ["🛡️ Scam Shield", "💰 Smart Budget", "📖 About"]
)

with tab_scam:
    from app.scam_ui import render_scam_tab
    render_scam_tab(adapter=adapter, retriever=retriever, classifier=classifier)

with tab_budget:
    from app.budget_ui import render_budget_tab
    render_budget_tab(adapter=adapter)

with tab_about:
    from app.about_ui import render_about_tab
    render_about_tab()
