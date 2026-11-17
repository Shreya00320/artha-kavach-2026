# 🛡️ Artha Kavach

> **"An AI money coach that protects you from UPI scams, builds your budget from bank SMS, and never says anything it can't prove."**

Built for **Arthaton 2026** — *AI for Finance* hackathon.  
Target users: students and first-job earners in India.

---

## ✨ What it does

One app for the money problems students and first-job earners in India actually hit:
UPI fraud, "where did my salary go?", saving for goals, and tax-regime confusion.

| Tab | What you can do |
|-----|-----------------|
| 🛡️ **Scam Shield** | **Check a message** (SMS / WhatsApp / UPI collect request, English · Hindi · Hinglish) → Scam / Suspicious / Safe with highlighted red flags and a cited Trust Receipt · **Check a link** offline (lookalike bank domains, shorteners, APKs — the link is never opened) · **Scan many messages** at once · **🆘 I've been scammed**: golden-hour action plan (1930, bank block, RBI zero-liability window) + a ready-to-paste cybercrime.gov.in complaint |
| 💰 **Smart Budget** | Paste bank SMS or upload a CSV → categorised spending, 50/30/20, nudges · **transfers to people kept out of spending** · **refunds netted off** · **salary-cycle months** (e.g. 27th → 26th) · **subscription tracker** with yearly cost · **unusual-payment alerts only** (no alert fatigue) · small-spend (chai/auto) bucket · weekly trend · **fix any category** and everything recomputes · **CSV export** |
| 🎯 **Goals & Tax** | Emergency fund tracker · multi-goal plan funded by priority · SIP calculator · EMI + prepayment savings · step-up "Save More Tomorrow" plan · tax regime comparison — pre-filled from your budget |
| ↳ 🧾 **Tax** (inside Goals & Tax) | Old vs new regime for **FY 2026-27** with 87A rebate, marginal relief, deduction caps, and the break-even deduction amount; 80C/80D/NPS pre-filled from payments found in your SMS |
| 💬 **Ask Artha** | Chat about your money ("Can I afford a ₹15,000 phone?", "Where can I cut?"). Answers use engine-computed numbers only; an AI reply containing any other number is rejected |
| 🔍 **Trust Receipt** | Every AI output carries its evidence: sources, verified claims, code-computed numbers, and which detectors agreed |

**Works offline** — without an API key, everything except the LLM judge, claim verifier and AI phrasing still works.
**Private by design** — data lives only in your session; a sidebar button clears it.

## 🚀 Live demo

> [![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://artha-kavach-2026-for-arthathon.streamlit.app)

One-click sample data is built in — no account needed to explore.
*(If the link asks you to sign in, the Streamlit app's sharing is set to private — make it public in the Streamlit Cloud settings.)*

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

Copy `.env.example` to `.env` (or add them to Streamlit Secrets) and fill in:

| Variable | Required | Description |
|----------|----------|-------------|
| `GEMINI_API_KEY` | Optional | Google AI Studio API key — enables LLM features (`LLM_API_KEY` is also accepted) |
| `LLM_PROVIDER` | Optional | `gemini` (default) or `mock` |
| `LLM_MODEL` | With a key | e.g. `gemini-3.8-flash` |
| `EMBEDDING_MODEL` | With a key | e.g. `gemini-embedding-001` |
| `LLM_CACHE_ENABLED` | Optional | `true` (default) — caches LLM responses to disk |

> ⚠️ `gemini-2.0-flash` (shut down 1 Jun 2026) and `text-embedding-004` (shut down 14 Jan 2026) no longer work.
> If your deployment still uses them, update the secrets. The app rebuilds its knowledge-base index automatically
> when the embedding model changes. Check [Gemini deprecations](https://aistudio.google.com/docs/deprecations).

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

> Run yourself: `python -m eval.quick_eval` (needs only scikit-learn) or `python -m eval.run_eval` (full report, needs pandas/matplotlib; add `--llm` with an API key)
> On your own real messages: put a CSV with `text,label` columns in `data/private/` (git-ignored) and run `python -m eval.real_eval data/private/real_sms.csv` (add `--llm` to include the AI judge)

### Scam detection — 47-message held-out test set (offline, no LLM)

| Detector | Macro F1 | Scam F1 | Suspicious F1 | Safe F1 | Safe msgs flagged |
|----------|----------|---------|---------------|---------|-------------------|
| Rules baseline | 0.55 | 0.77 | 0.17 | 0.71 | 0 |
| ML classifier (word + char n-grams) | 0.79 | 0.87 | 0.57 | 0.94 | 1 |
| **Combined pipeline (offline)** | **0.82** | **0.89** | **0.62** | **0.94** | 1 |

- Previous version: rules 0.47, classifier 0.72, combined **0.47** — the old score combination let the
  classifier contribute at most 40%, so it could never raise a verdict to "scam" on its own. Now the more
  severe of the two verdicts wins.
- Rules engine: **100% precision on scam** — no safe message is flagged by rules alone.
- The `suspicious` class is still the hardest; the LLM judge helps most here.

### SMS parser — 96-message sample (91 transactions + 5 non-transactions)

| Mode | Transactions read | Amount accuracy | Non-transactions wrongly read |
|------|-------------------|-----------------|-------------------------------|
| Regex-only (before) | 65.6% | 100% | 0 |
| **Regex-only (now)** | **100%** | **100%** | **0** |

*The new generic templates were written while looking at this sample, so treat 100% as optimistic;
`tests/test_features.py` adds formats that are not in the sample (SBI UPI "debited by", "INR", dd/mm/yyyy, "Paid Rs … to").*

### Budget engine invariant checks
**16 / 16 checks pass** — all arithmetic is verified, including transfers and refunds.

**Honest caveats:**
- Test sets are synthetic (155 labelled messages, 96 SMS). Real-world performance may differ.
- Hinglish subset is small (5 test examples) — treat as directional only.

## 🗂️ Project structure

```
artha-kavach-2026/
├── app/                  ← Streamlit UI
│   ├── main.py           ← Entry point, caching, 5-tab layout, demo story, privacy controls
│   ├── scam_ui.py        ← Scam Shield: message · link · bulk scan · I've been scammed
│   ├── budget_ui.py      ← Smart Budget: overview · alerts · subscriptions · transactions · tax hints
│   ├── goals_ui.py       ← Emergency fund · goals · SIP · EMI · step-up saving
│   ├── tax_ui.py         ← Old vs new regime
│   ├── chat_ui.py        ← Ask Artha
│   ├── about_ui.py       ← About / How it Works tab
│   ├── components.py     ← Reusable render functions
│   └── styles.py         ← CSS tokens
│
├── core/                 ← Money logic (pure Python, no AI in arithmetic)
│   ├── parser.py         ← Hybrid SMS parser (bank templates + generic templates + LLM fallback)
│   ├── categoriser.py    ← Merchant lookup, UPI-handle names, P2P & refund detection, LLM fallback
│   ├── budget_engine.py  ← 50/30/20, transfers/refunds, pace, recurring
│   ├── insights.py       ← Subscriptions, anomalies, small spends, weekly trend, salary cycle, tax tags, export
│   ├── goals.py          ← SIP, EMI, prepayment, emergency fund, multi-goal planner
│   ├── tax.py            ← FY 2026-27 old vs new regime calculator
│   ├── assistant.py      ← Ask Artha: rules answers + LLM phrasing with number post-check
│   ├── nudges.py         ← Nudge writer (LLM or rule-based fallback)
│   ├── savings.py        ← Flat vs step-up savings plans
│   └── trust_receipt.py  ← Trust Receipt builder (shared by all modules)
│
├── scam/                 ← Scam Shield pipeline
│   ├── rules.py          ← 50+ regex/keyword rules, noisy-OR scoring
│   ├── classifier.py     ← TF-IDF (word + char n-grams) + Logistic Regression (no pandas needed)
│   ├── llm_judge.py      ← LLM verdict + rules/classifier fallback
│   ├── verifier.py       ← Claim verification against KB
│   ├── link_check.py     ← Offline URL inspection (official domains, lookalikes, shorteners…)
│   ├── emergency.py      ← "I've been scammed" action plan + complaint draft
│   └── pipeline.py       ← Full orchestration: rules→ML→LLM→verify→receipt
│
├── rag/                  ← Retrieval-augmented generation
│   ├── ingest.py         ← Build vector index from KB docs (FAISS, or numpy if FAISS can't load)
│   └── retrieve.py       ← Semantic search + citation formatting
│
├── llm/                  ← LLM abstraction layer (adapter, versioned prompts, Pydantic schemas)
│
├── data/
│   ├── scam_eval.csv     ← 155 labelled messages (synthetic, seed=42, 70/30 split)
│   ├── sample_sms.csv    ← 96 synthetic bank/UPI SMS
│   └── kb/               ← 21 knowledge-base documents (RBI, NPCI, I4C/MHA, DoT, SEBI…)
│
├── eval/
│   ├── quick_eval.py     ← Lightweight evaluation (scikit-learn only)
│   ├── run_eval.py       ← Full evaluation suite with charts
│   └── results/          ← JSON + CSV + PNG outputs
│
├── tests/                ← 151 tests incl. headless end-to-end UI tests
├── .env.example
├── requirements.txt
├── ARCHITECTURE.md
└── SPEC.md               ← Original product specification
```

## 🧪 Running tests

```bash
# Everything (151 tests: unit + headless Streamlit UI tests; no API key needed)
python -m pytest tests/ -v

# Just the new features (tax, goals, insights, assistant, link checker, rules, parser formats)
python -m pytest tests/test_features.py -v

# End-to-end UI smoke test (runs the real app headlessly via streamlit.testing)
python -m pytest tests/test_app_smoke.py -v
```

FAISS is optional: if it cannot load (e.g. blocked DLL on some Windows machines), retrieval uses an exact numpy index.

## 📚 Data sources

All Knowledge Base documents are from official / reputable public sources:

| Source | Topics |
|--------|--------|
| RBI (rbi.org.in) | UPI safety, OTP guidance, financial literacy |
| NPCI (npci.org.in) | Collect-request scam awareness |
| MeitY / Cyber Dost | Phishing, KYC fraud, job scams |
| cybercrime.gov.in / I4C (MHA) | How to report, helpline 1930, 'digital arrest', task & investment scams |
| RBI circular RBI/2017-18/15 | Zero liability for unauthorised electronic transactions reported in time |
| DoT Sanchar Saathi (Chakshu) | Reporting fraud calls / SMS / WhatsApp |
| Income Tax Act / Budget 2026 | FY 2026-27 slabs, standard deduction, 87A rebate |
| Thaler & Benartzi (2004) | Save More Tomorrow (SMarT) research |

Datasets (`scam_eval.csv`, `sample_sms.csv`) are **synthetic** — clearly labelled in the files.

---

## ⚠️ Limitations & what it does NOT do

- ❌ No real money movement — educational tool only
- ❌ No live trading or NSE data; no bank account linking (SMS/CSV only — by design, for privacy)
- ❌ Tax calculator skips surcharge (> ₹50 L), capital gains and senior-citizen slabs
- ❌ Link checker inspects the address only; it cannot see what a page contains
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
