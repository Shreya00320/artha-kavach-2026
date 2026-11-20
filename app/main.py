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
    api_key  = (os.getenv("GROQ_API_KEY", "") if provider == "groq" else os.getenv("GEMINI_API_KEY", "")) \
        or os.getenv("LLM_API_KEY", "")
    if not api_key and provider in ("gemini", "groq"):
        return None
    try:
        from llm.adapter import LLMAdapter
        return LLMAdapter()
    except Exception as exc:
        logging.warning("LLM adapter init failed: %s", exc)
        return None


@st.cache_resource(show_spinner="Loading knowledge base…")
def _get_retriever():
    """Return a Retriever from the saved FAISS index.

    If the index has not been built yet (e.g. fresh Streamlit Cloud deploy),
    build it automatically from data/kb/ before returning.
    Returns None if no API key is set or if FAISS is unavailable.
    """
    # Embeddings use Gemini; with another LLM provider the chat uses its keyword fallback.
    if os.getenv("LLM_PROVIDER", "gemini") != "gemini":
        return None
    api_key = os.getenv("GEMINI_API_KEY", "") or os.getenv("LLM_API_KEY", "")
    if not api_key:
        return None
    try:
        from google import genai
        from rag.ingest import build_index, load_index
        from rag.retrieve import Retriever

        client = genai.Client(api_key=api_key)
        cache_dir = ".cache"

        # Try loading an existing index first (fast path)
        try:
            index = load_index(cache_dir)
            wanted = os.getenv("EMBEDDING_MODEL", "")
            if wanted and index.embedding_model != wanted:
                # Index was embedded with another (possibly retired) model: query
                # vectors would not match, so rebuild with the configured model.
                raise FileNotFoundError(f"index model {index.embedding_model} != {wanted}")
            logging.info("Vector index loaded from cache (%d docs).", index.index.ntotal)
        except FileNotFoundError:
            # Index not built yet — build it now (runs once per deploy)
            logging.info("FAISS index not found — building from data/kb/ …")
            with st.spinner("🔨 Building knowledge base index (one-time, ~30 s)…"):
                index = build_index(
                    kb_dir="data/kb",
                    cache_dir=cache_dir,
                    client=client,
                )
            logging.info("FAISS index built (%d docs).", index.index.ntotal)

        return Retriever(index, client)
    except Exception as exc:
        logging.warning("Retriever init failed: %s", exc)
        return None


@st.cache_resource(show_spinner="Loading scam model…")
def _get_classifier():
    """Return the deep scam model (shipped weights, numpy inference); fall back to TF-IDF + LR."""
    try:
        from scam.deep_model import load_default
        clf = load_default()
        if clf is not None:
            return clf
    except Exception as exc:
        logging.warning("Deep model init failed: %s", exc)
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

from app.i18n import t

with st.sidebar:
    _lang_label = st.radio("Language / भाषा", ["English", "हिन्दी"], horizontal=True, key="lang_choice")
LANG = "hi" if _lang_label == "हिन्दी" else "en"

st.markdown(
    f"""
<div class="hero">
  <div class="hero-title">🛡️ Artha Kavach</div>
  <div class="hero-tag">{t("tag", LANG)}</div>
  <div class="hero-chips">
    <span>{t("chip1", LANG)}</span><span>{t("chip2", LANG)}</span>
    <span>{t("chip3", LANG)}</span><span>{t("chip4", LANG)}</span><span>{t("chip5", LANG)}</span>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Status sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown(f"### {t('status', LANG)}")
    adapter    = _get_adapter()
    retriever  = _get_retriever()
    classifier = _get_classifier()

    st.markdown(
        f"{'✅' if adapter    else '⚠️'} **LLM** — "
        f"{'Live (' + adapter.provider.title() + ' · ' + adapter.model + ')' if adapter else 'Offline (rules fallback)'}"
    )
    st.markdown(
        f"{'✅' if retriever  else '⚠️'} **Knowledge base** — "
        f"{'Loaded ({} docs)'.format(retriever.n_documents) if retriever else 'Built-in keyword search (no embeddings)'}"
    )
    st.markdown(
        f"{'✅' if classifier else '⚠️'} **Deep scam model** — "
        f"{'Trained' if classifier else 'Not available'}"
    )

    if not adapter:
        st.info(
            "Set `LLM_PROVIDER=groq` + `GROQ_API_KEY` (free) or `GEMINI_API_KEY` in `.env` or Streamlit Secrets to enable the LLM judge.  \n"
            "The app works offline using rules + ML only."
        )

    st.divider()
    st.markdown(f"### {t('demo', LANG)}")
    st.caption("One click loads a 'digital arrest' scam message and a month of bank SMS "
               "that includes the ₹25,000 the victim already paid.")
    if st.button("Load demo story", width="stretch", key="btn_demo_story"):
        from app.demo import load_demo_story
        load_demo_story()
        st.success("Loaded — start in 🛡️ Scam Shield, then 💰 Smart Budget, then 💬 Ask Artha.")

    st.divider()
    st.markdown(f"### {t('privacy', LANG)}")
    st.caption(
        "Messages you paste are processed in this session only and are not stored by the app. "
        "With an API key set, text is sent to the LLM provider for analysis; without one, "
        "everything runs locally."
    )
    if st.button(t("clear", LANG), width="stretch"):
        for k in list(st.session_state.keys()):
            if k != "lang_choice":
                del st.session_state[k]
        st.rerun()

    st.divider()
    st.markdown("**Arthaton 2026** — AI for Finance")
    st.caption(t("disclaimer", LANG))

# ---------------------------------------------------------------------------
# Main tabs (Smart Budget renders before Goals/Tax/Ask so they see fresh data)
# ---------------------------------------------------------------------------

tab_scam, tab_budget, tab_goals, tab_chat, tab_about = st.tabs(
    [t("tab_scam", LANG), t("tab_budget", LANG), t("tab_goals", LANG), t("tab_chat", LANG), t("tab_about", LANG)]
)

with tab_scam:
    from app.scam_ui import render_scam_tab
    render_scam_tab(adapter=adapter, retriever=retriever, classifier=classifier)

with tab_budget:
    from app.budget_ui import render_budget_tab
    render_budget_tab(adapter=adapter)

with tab_goals:
    from app.goals_ui import render_goals_tab
    render_goals_tab()

with tab_chat:
    from app.chat_ui import render_chat_tab
    render_chat_tab(adapter=adapter)

with tab_about:
    from app.about_ui import render_about_tab
    render_about_tab()
