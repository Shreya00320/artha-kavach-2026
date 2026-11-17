# 🛡️ Artha Kavach

> **"An AI money coach that protects you from UPI scams, builds your budget from bank SMS, and never says anything it can't prove."**

Built for **Arthaton 2026** — *AI for Finance* hackathon.  
Target users: students and first-job earners in India.

---

## ✨ What it does

| Feature | Description |
|---------|-------------|
| 🛡️ **Scam Shield** | Paste any SMS / WhatsApp / UPI collect-request → instant verdict (Scam / Suspicious / Safe) with highlighted red flags, plain-English advice, and a cited Trust Receipt |
| 💰 **Smart Budget** | Paste bank SMS or upload a CSV → auto-categorised expenses, 50/30/20 breakdown, personalised nudges, recurring-payment detection, and a savings planner |
| 🔍 **Trust Receipt** | Every AI output carries its evidence: sources used, verified claims, code-computed numbers, and which detectors agreed |

**Works offline** — if no API key is set, the app falls back to a rules engine + ML classifier so the demo never breaks.

---

## 🚀 Live demo

> [![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://artha-kavach.streamlit.app)

One-click sample data is built in — no account needed to explore.

---

## 🏃 Quick start (local)

### Prerequisites
- Python 3.11 or 3.12
- Git

```bash
# 1. Clone
git clone https://github.com/Shreya00320/artha-kavach-2026.git
cd artha-kavach-2026

# 2. Create a virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment (optional — app works without API key)
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY (get one free at aistudio.google.com)

# 5. Run
streamlit run app/main.py
```

The app opens at **http://localhost:8501**.

> **No API key?** The Scam Shield still works via rules + ML classifier.  
> The Smart Budget still works via regex parser + rule-based nudges.  
> Set `GEMINI_API_KEY` to unlock the LLM judge, claim verifier, and LLM nudges.

---

## ⚙️ Environment variables

Copy `.env.example` to `.env` and fill in:

| Variable | Required | Description |
|----------|----------|-------------|
| `GEMINI_API_KEY` | Optional | Google AI Studio API key — enables LLM features (`LLM_API_KEY` is also accepted) |
| `LLM_PROVIDER` | Optional | `gemini` (default) or `mock` |
| `LLM_MODEL` | Optional | e.g. `gemini-2.0-flash` |
| `EMBEDDING_MODEL` | Optional | e.g. `models/text-embedding-004` |
| `LLM_CACHE_ENABLED` | Optional | `true` (default) — caches LLM responses to disk |

---

## 📐 Architecture

```
User input (SMS text / CSV)
           │
           ▼
┌──────────────────────────────────────────────┐
│               Artha Kavach                   │
│                                              │
│  ┌───────────────┐   ┌────────────────────┐  │
│  │  Scam Shield  │   │   Smart Budget     │  │
│  │               │   │                    │  │
│  │ 1. Rules      │   │ 1. SMS Parser      │  │
│  │    engine     │   │    (regex + LLM)   │  │
│  │ 2. ML (TF-IDF │   │ 2. Categoriser     │  │
│  │    + LogReg)  │   │    (lookup + LLM)  │  │
│  │ 3. LLM judge  │   │ 3. Budget engine   │  │
│  │    + RAG      │   │    (pure Python)   │  │
│  │ 4. Claim      │   │ 4. Nudge writer    │  │
│  │    verifier   │   │ 5. Savings planner │  │
│  └──────┬────────┘   └────────┬───────────┘  │
│         └──────────┬──────────┘              │
│                    ▼                         │
│             Trust Receipt                    │
│  (sources · verified claims · detector       │
│   votes · code-computed values)              │
└──────────────────────────────────────────────┘
           │
           ▼
  Verdict + Explanation + Evidence
```

**Design principle:** use plain code where code is reliable (arithmetic, regex parsing), a small classical model for cheap fast verdicts, and the LLM only where language understanding is needed.

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the full technical diagram.

---

## 📊 Evaluation results

> Run yourself: `python -m eval.run_eval` (offline) or `python -m eval.run_eval --llm` (requires API key)

### Scam detection — 47-message held-out test set

| Detector | Macro F1 | Scam F1 | Safe F1 |
|----------|----------|---------|---------|
| Rules baseline | 0.47 | 0.60 | 0.67 |
| **ML Classifier** | **0.72** | **0.80** | **0.89** |
| Combined pipeline (offline) | ~0.72† | — | — |

†*Estimated from saved per-detector predictions after the verdict-combination fix (the more severe of the rules and classifier verdicts wins). Re-run `python -m eval.run_eval` to refresh. Previously 0.47 because the classifier could not raise a verdict to "scam" on its own.*

- Rules engine: **100% precision on scam** — zero false positives for safe messages
- ML classifier (Hinglish subset, 5 msgs): F1 = **0.82** vs rules 0.36
- LLM judge improves edge cases further (run with `--llm`)

### SMS parser — 96-message sample set

| Mode | Success rate | Amount accuracy |
|------|-------------|-----------------|
| Regex-only | 65.6% | **100%** |
| Regex + LLM fallback | ~90%* | ~95%* |

*\*LLM fallback estimated; requires API key to benchmark.*

### Budget engine invariant checks
**16 / 16 checks pass** — all arithmetic is mathematically verified.

**Honest caveats:**
- Test set is synthetic (155 labelled examples). Real-world performance may differ.
- Hinglish subset is small (5 test examples) — treat as directional only.
- The `suspicious` class is hardest to separate; LLM judge helps most here.

---

## 🗂️ Project structure

```
artha-kavach-2026/
├── app/                  ← Streamlit UI
│   ├── main.py           ← Entry point, caching, 3-tab layout
│   ├── scam_ui.py        ← Scam Shield tab
│   ├── budget_ui.py      ← Smart Budget tab
│   ├── about_ui.py       ← About / How it Works tab
│   ├── components.py     ← Reusable render functions
│   └── styles.py         ← CSS tokens
│
├── core/                 ← Budget pipeline (pure Python, no AI in arithmetic)
│   ├── parser.py         ← Hybrid SMS parser (regex + LLM fallback)
│   ├── categoriser.py    ← Merchant categoriser (lookup + LLM fallback)
│   ├── budget_engine.py  ← All budget math: 50/30/20, pace, recurring
│   ├── nudges.py         ← Nudge writer (LLM or rule-based fallback)
│   ├── savings.py        ← Flat vs step-up savings plans
│   └── trust_receipt.py  ← Trust Receipt builder (shared by all modules)
│
├── scam/                 ← Scam Shield pipeline
│   ├── rules.py          ← 10+ regex/keyword rules, noisy-OR scoring
│   ├── classifier.py     ← TF-IDF + Logistic Regression (3-class)
│   ├── llm_judge.py      ← LLM verdict + rules-only fallback
│   ├── verifier.py       ← Claim verification against KB
│   └── pipeline.py       ← Full orchestration: rules→ML→LLM→verify→receipt
│
├── rag/                  ← Retrieval-augmented generation
│   ├── ingest.py         ← Build FAISS vector index from KB docs
│   └── retrieve.py       ← Semantic search + citation formatting
│
├── llm/                  ← LLM abstraction layer
│   ├── adapter.py        ← Gemini API wrapper (retry, cache, mock)
│   ├── prompts.py        ← All prompts as versioned constants
│   └── schemas.py        ← Pydantic output schemas
│
├── data/
│   ├── scam_eval.csv     ← 155 labelled SMS (synthetic, seed=42, 70/30 split)
│   ├── sample_sms.csv    ← 120 synthetic bank/UPI SMS (one month)
│   └── kb/               ← Knowledge base documents (RBI, NPCI, MeitY…)
│
├── eval/
│   ├── run_eval.py       ← Full evaluation suite
│   └── results/          ← JSON + CSV + PNG outputs
│
├── tests/                ← 72 unit tests (all pass)
├── .env.example          ← Environment variable template
├── requirements.txt
├── ARCHITECTURE.md
└── SPEC.md               ← Original product specification
```

---

## 🧪 Running tests

```bash
# All tests (72 total — 5 FAISS DLL failures on some Windows builds, pre-existing)
python -m pytest tests/ -v

# Just scam tests (27 — all pass, no API key needed)
python -m pytest tests/test_scam.py -v

# Just budget/core tests
python -m pytest tests/test_core.py tests/test_adapter.py -v
```

---

## 📚 Data sources

All Knowledge Base documents are from official / reputable public sources:

| Source | Topics |
|--------|--------|
| RBI (rbi.org.in) | UPI safety, OTP guidance, financial literacy |
| NPCI (npci.org.in) | Collect-request scam awareness |
| MeitY / Cyber Dost | Phishing, KYC fraud, job scams |
| cybercrime.gov.in | How to report, national helpline 1930 |
| Thaler & Benartzi (2004) | Save More Tomorrow (SMarT) research |

Datasets (`scam_eval.csv`, `sample_sms.csv`) are **synthetic** — clearly labelled in the files.

---

## ⚠️ Limitations & what it does NOT do

- ❌ No real money movement — educational tool only
- ❌ No live trading or NSE data
- ❌ Classifier trained on synthetic data — real-world accuracy may differ
- ❌ Unusual or bank-specific SMS formats may not parse correctly
- ❌ LLM calls add latency (~2–5 s) — app degrades gracefully without them
- ❌ Not a substitute for professional financial or legal advice

---

## ⚖️ Disclaimer

Artha Kavach is an educational demonstration tool built for a hackathon. It does not provide financial, legal, or investment advice. Always verify suspicious messages with your bank directly or report them at [cybercrime.gov.in](https://cybercrime.gov.in) / helpline **1930**.

---

## 👥 Team

Built for Arthaton 2026 — *"AI for Finance"* — submission deadline 22 Nov 2026.
