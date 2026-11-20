# 🛡️ Artha Kavach

> **"An AI money coach that protects you from UPI scams, builds your budget from bank SMS, answers your money questions, and never says anything it can't prove."**

Built for **Arthaton 2026** — *AI for Finance* hackathon.
Target users: students and first-job earners in India.

---

## ✨ What it does

One app for the money problems students and first-job earners in India actually hit:
UPI fraud, "where did my salary go?", saving for goals, tax-regime confusion, and "I just got my first
salary — now what?".

| Tab | What you can do |
|-----|-----------------|
| 🛡️ **Scam Shield** | **Check a message** (SMS / WhatsApp / UPI collect request, English · Hindi · Hinglish) → Scam / Suspicious / Safe with highlighted red flags and a cited Trust Receipt · **Check a link** offline (lookalike bank domains, shorteners, APKs — the link is never opened) · **Scan many messages** at once · **🧠 names the manipulation tactic** (fake authority, urgency, greed, trust hijack) · **🆘 I've been scammed**: golden-hour action plan (1930, bank block, RBI zero-liability window) + a ready-to-paste cybercrime.gov.in complaint |
| 💰 **Smart Budget** | Paste bank SMS, or upload a **bank-statement CSV** or SMS CSV → categorised spending, 50/30/20, nudges · **transfers to people kept out of spending** · **refunds netted off** · **salary-cycle months** (e.g. 27th → 26th) · **subscription tracker** with yearly cost · **unusual-payment alerts only** (no alert fatigue) · small-spend (chai/auto) bucket · weekly trend · **fix any category** and everything recomputes · **CSV export** · **📄 monthly money report (PDF)** |
| 🎯 **Goals & Tax** | Emergency fund tracker · multi-goal plan funded by priority · SIP calculator · EMI + prepayment savings · step-up "Save More Tomorrow" plan · **🌱 first-salary guide** (what to do, in order) · **🏠 Home**: affordability + rent-vs-buy · tax regime comparison — pre-filled from your budget |
| ↳ 🧾 **Tax** (inside Goals & Tax) | Old vs new regime for **FY 2026-27** with 87A rebate, marginal relief, deduction caps, and the break-even deduction amount; 80C/80D/NPS pre-filled from payments found in your SMS |
| 💬 **Ask Artha** | A conversational money coach. Ask **general finance questions** ("What is a SIP?", "ELSS vs PPF?", "Is a credit card a good idea?", "Which money books should a beginner read?") answered from a **92-document knowledge base** (scam advisories + finance education + 25 summaries of well-known money books), or **questions about your own data** ("Can I afford a ₹15,000 phone?", "Where can I cut?"). Every figure comes from the budget engine or the cited passage; an AI reply containing any other number is rejected. It refuses to pick stocks/funds/crypto, predict markets, or follow prompt-injection, and warns about "guaranteed return" bait |
| 🔍 **Trust Receipt** | Every AI output carries its evidence: sources, verified claims, code-computed numbers, and which detectors agreed |

**Bilingual shell** — English / हिन्दी toggle for headings and tabs. **Behavioural nudges** — spending shown as hours of your work; pay-yourself-first on salary day.

**Works offline** — without an API key, everything except the LLM judge, claim verifier and AI phrasing still works (the scam model, chat knowledge base, budget, goals, tax and PDF report are all local).
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

# 4. Configure environment (optional — app works without an API key)
cp .env.example .env          # Windows: copy .env.example .env
# Edit .env — see "Environment variables" below (a free Groq key is the easiest)

# 5. Check the LLM connection (optional)
python smoke_test.py

# 6. Run
streamlit run app/main.py
```

The app opens at **http://localhost:8501**.

> **No API key?** Scam Shield still works (rules + deep model), Ask Artha answers from the local knowledge base,
> and Smart Budget works via the regex parser + rule-based nudges.
> Add a key to unlock the LLM judge, claim verifier, LLM nudges and LLM phrasing in chat.

---

## ⚙️ Environment variables

Copy `.env.example` to `.env` (or add them to Streamlit Secrets). **Never commit `.env` or paste keys into chats/issues** — it is git-ignored.

**Option A — Groq (free tier, recommended for local use)**

```
LLM_PROVIDER=groq
GROQ_API_KEY=<key from https://console.groq.com>
LLM_MODEL=openai/gpt-oss-120b      # default if unset; openai/gpt-oss-20b is the smaller/faster option
```

**Option B — Google Gemini**

```
LLM_PROVIDER=gemini
GEMINI_API_KEY=<key from https://aistudio.google.com>
LLM_MODEL=gemini-3.8-flash
EMBEDDING_MODEL=gemini-embedding-001
```

| Variable | Required | Description |
|----------|----------|-------------|
| `LLM_PROVIDER` | Optional | `gemini` (default), `groq`, or `mock` (offline tests) |
| `GROQ_API_KEY` | With `groq` | Groq API key (`LLM_API_KEY` is also accepted) |
| `GEMINI_API_KEY` | With `gemini` | Google AI Studio key (`LLM_API_KEY` is also accepted) |
| `LLM_MODEL` | With a key | Groq default `openai/gpt-oss-120b`; for Gemini e.g. `gemini-3.8-flash` |
| `EMBEDDING_MODEL` | Gemini only | e.g. `gemini-embedding-001` — used for the FAISS/RAG index in Scam Shield |
| `LLM_TEMPERATURE`, `LLM_TIMEOUT_SECONDS`, `LLM_MAX_RETRIES` | Optional | Defaults `0.1`, `30`, `3` |
| `LLM_CACHE_ENABLED`, `LLM_CACHE_DIR` | Optional | `true` / `.cache/llm` — caches LLM responses to disk |

**Notes**
- With `groq`, Gemini embeddings are not used: the Scam Shield RAG index is skipped and the chat advisor uses its
  built-in offline TF-IDF retriever over the same knowledge base.
- Groq's free tier has a tokens-per-minute cap (8,000 TPM on `gpt-oss-120b` at the time of writing). The adapter
  honours the "try again in Ns" hint on HTTP 429 and caches responses, so reruns are cheap.
- `gemini-2.0-flash` (shut down 1 Jun 2026) and `text-embedding-004` (shut down 14 Jan 2026) no longer work.
  The app rebuilds its knowledge-base index automatically when the embedding model changes.
  Check [Gemini deprecations](https://aistudio.google.com/docs/deprecations).

## 📐 Architecture

```
User input (SMS text / CSV / chat message)
           │
           ▼
┌──────────────────────────────────────────────────────────────┐
│                        Artha Kavach                          │
│                                                              │
│  ┌───────────────┐  ┌────────────────┐  ┌─────────────────┐  │
│  │  Scam Shield  │  │  Smart Budget  │  │   Ask Artha     │  │
│  │ 1. Rules      │  │ 1. SMS/CSV     │  │ 1. Safety guards│  │
│  │    engine     │  │    parser      │  │ 2. Scam routing │  │
│  │ 2. Deep model │  │ 2. Categoriser │  │ 3. Your numbers │  │
│  │    (NumPy)    │  │ 3. Budget      │  │    (engine)     │  │
│  │ 3. LLM judge  │  │    engine      │  │ 4. Knowledge    │  │
│  │    + RAG      │  │    (pure       │  │    base (92     │  │
│  │ 4. Claim      │  │    Python)     │  │    docs) + LLM  │  │
│  │    verifier   │  │ 4. Nudges, PDF │  │    phrasing     │  │
│  └──────┬────────┘  └───────┬────────┘  └────────┬────────┘  │
│         └───────────────────┼────────────────────┘           │
│                             ▼                                │
│                      Trust Receipt                           │
│     (sources · verified claims · detector votes ·            │
│      code-computed values · number post-check)               │
└──────────────────────────────────────────────────────────────┘
           │
           ▼
  Verdict / answer + Explanation + Evidence
```

**Design principle:** use plain code where code is reliable (arithmetic, regex parsing), a small local model for cheap fast
verdicts, and the LLM only where language understanding is needed — and never let it introduce a number we did not compute.

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the full technical diagram.

---

## 🧠 Scam Shield deep model

`scam/deep_model.py` is a small neural network (hashed word + character n-gram embeddings → two hidden layers →
safe / suspicious / scam, ensemble of 3). It is trained with PyTorch (`python -m scam.train_deep`, GPU used if available)
and the weights ship in `models/scam_dl.npz` (~5.7 MB); the running app uses **NumPy only** (no torch needed).

Training data: `data/scam_eval.csv` (train split), generated messages (`data/build_scam_train.py`), and
~2,000 real everyday texts from the UCI *SMS Spam Collection* ham messages
(Almeida & Hidalgo, 2011, CC BY 4.0 — re-download with `data/fetch_sms_ham.py`; not committed).
Hand-written held-out sets (`data/ordinary_text_eval.csv`, `data/scam_heldout.csv`) are never trained on.

`data/fetch_vinit_ham.py` can extract extra ordinary texts from a third-party SMS dataset (no licence stated; A/B tests
showed no measurable gain), so it is **off by default**: `python -m scam.train_deep --vinit-n=1200`.

## 📄 Monthly money report (PDF)

Smart Budget → Overview → **Download my money report (PDF)**. `core/report.py` is a small dependency-free
PDF writer (built-in Helvetica fonts, amounts shown as "Rs"); every figure comes from the budget engine.

---

## 📊 Evaluation results

> Reproduce: `python -m eval.quick_eval` (needs only scikit-learn), `python -m eval.run_eval` (full report; pandas/matplotlib),
> `python -m eval.chat_eval` (chat; add `--llm` with a key), `python -m scam.train_deep --no-save` (deep-model metrics).
> On your own real messages: put a CSV with `text,label` columns in `data/private/` (git-ignored) and run
> `python -m eval.real_eval data/private/real_sms.csv` (add `--llm` to include the AI judge).
> The scam evals now run the same pipeline the app uses (the deep model when `models/scam_dl.npz` is present).

### Scam detection (offline, no LLM)

47-message held-out test split of `data/scam_eval.csv`:

| Detector | Macro F1 | Scam F1 | Suspicious F1 | Safe F1 |
|----------|----------|---------|---------------|---------|
| Rules baseline | 0.55 | 0.77 | 0.17 | 0.71 |
| TF-IDF + LogReg (word + char n-grams) | 0.79 | 0.87 | 0.57 | 0.94 |
| **Pipeline offline (rules + deep model)** | **0.78** | 0.85 | 0.60 | 0.88 |

On this small test split the deep model is about equal to TF-IDF. Its advantage is **fewer false alarms on ordinary text**
and **catching newer scams**, which the 47-message split does not measure:

| Set (deep model, shipped weights) | Result |
|-----------------------------------|--------|
| Real everyday SMS (300 UCI ham messages, never trained on) | **2%** false alarms |
| Hand-written ordinary text (76 messages) | 2.6% flagged through the full pipeline (8% by the model alone) |
| New hand-written scams (38 messages, never trained on) | **97%** caught (not "safe"); 77% labelled exactly "scam" |

- Rules engine: **100% precision on scam** — no safe message is flagged by rules alone.
- The `suspicious` class is the hardest; the LLM judge helps most here.
- The pipeline's thresholds (`CLF_SCAM_MIN=0.50`, `CLF_FLAG_MIN=0.85` in `scam/llm_judge.py`) are tuned for the deep model.

### Ask Artha (offline rules + retrieval; `python -m eval.chat_eval`)

| Set | n | Result |
|-----|---|--------|
| Knowledge QA (right source retrieved) | 168 | 99% answered, **99%** right source |
| Social-style / messy messages | 50 | **92%** correct |
| Adversarial (prompt injection, stock-pick requests, scam bait, off-topic) | 42 | **100%** correct |
| Numbers in knowledge answers not backed by a source | — | **0** violations |

Known gaps: very informal inputs ("bro my cousin says put everything in sip…") sometimes get "I'm not sure";
there is no multi-turn evaluation yet. LLM-mode results (`--llm`) have not been recorded yet.

### SMS parser — 96-message sample (91 transactions + 5 non-transactions)

| Mode | Transactions read | Amount accuracy | Non-transactions wrongly read |
|------|-------------------|-----------------|-------------------------------|
| Regex-only (before) | 65.6% | 100% | 0 |
| **Regex-only (now)** | **100%** | **100%** | **0** |

*The generic templates were written while looking at this sample, so treat 100% as optimistic;
`tests/test_features.py` adds formats that are not in the sample (SBI UPI "debited by", "INR", dd/mm/yyyy, "Paid Rs … to").*

### Budget engine invariant checks
**16 / 16 checks pass** — all arithmetic is verified, including transfers and refunds.

**Honest caveats:**
- Scam test sets are mostly synthetic or written by the developers (155 labelled messages + 38 held-out scams + 76 ordinary
  texts + 96 SMS), and the training templates were written by the same people — real-world performance may be lower.
  Fresh, real, held-out messages are still needed.
- Hinglish subset is small (5 test examples) — treat as directional only.
- Knowledge-base entries KB022–KB092 are our own plain-language summaries and are flagged `verified: false` until a human
  checks rates, tax limits and book attributions — see `data/kb/TODO_manual_verification.md`.

## 🗂️ Project structure

```
artha-kavach-2026/
├── app/                  ← Streamlit UI
│   ├── main.py           ← Entry point, caching, 5-tab layout, demo story, privacy controls
│   ├── scam_ui.py        ← Scam Shield: message · link · bulk scan · I've been scammed
│   ├── budget_ui.py      ← Smart Budget: overview · alerts · subscriptions · transactions · tax hints · PDF report
│   ├── goals_ui.py       ← Emergency fund · goals · SIP · EMI · step-up saving · first salary · home
│   ├── tax_ui.py         ← Old vs new regime
│   ├── chat_ui.py        ← Ask Artha (chat)
│   ├── starter_ui.py     ← First-salary guide
│   ├── about_ui.py       ← About / How it Works tab
│   ├── i18n.py, demo.py, components.py, styles.py
│
├── core/                 ← Money logic (pure Python, no AI in arithmetic)
│   ├── parser.py         ← Hybrid SMS parser (bank templates + generic templates + LLM fallback)
│   ├── statement.py      ← Bank-statement CSV → SMS-style rows
│   ├── categoriser.py    ← Merchant lookup, UPI-handle names, P2P & refund detection, LLM fallback
│   ├── budget_engine.py  ← 50/30/20, transfers/refunds, pace, recurring
│   ├── insights.py       ← Subscriptions, anomalies, small spends, weekly trend, salary cycle, tax tags, export
│   ├── goals.py, savings.py, realestate.py ← SIP/EMI/prepayment/step-up/affordability/rent-vs-buy
│   ├── tax.py            ← FY 2026-27 old vs new regime calculator
│   ├── advisor.py        ← Ask Artha: guards → scam routing → small talk → your numbers → KB answer (+ LLM phrasing)
│   ├── knowledge.py      ← Offline TF-IDF retriever over data/kb (no key needed)
│   ├── lang.py           ← Hindi/Hinglish query expansion (built, not yet wired — chat is English-only for now)
│   ├── assistant.py      ← Grounded answers about the user's own numbers + number post-check
│   ├── report.py         ← Dependency-free PDF writer for the money report
│   ├── nudges.py         ← Nudge writer (LLM or rule-based fallback)
│   ├── behaviour.py      ← Hours-of-work framing, pay-yourself-first
│   └── trust_receipt.py  ← Trust Receipt builder (shared by all modules)
│
├── scam/                 ← Scam Shield pipeline
│   ├── rules.py          ← 50+ regex/keyword rules, noisy-OR scoring
│   ├── deep_model.py     ← Neural classifier (NumPy inference); train_deep.py trains it with PyTorch
│   ├── classifier.py     ← TF-IDF + Logistic Regression fallback (no pandas needed)
│   ├── llm_judge.py      ← LLM verdict + rules/model fallback, tuned thresholds
│   ├── verifier.py       ← Claim verification against KB
│   ├── tactics.py        ← Names the manipulation tactic
│   ├── link_check.py     ← Offline URL inspection (official domains, lookalikes, shorteners…)
│   ├── emergency.py      ← "I've been scammed" action plan + complaint draft
│   └── pipeline.py       ← Full orchestration: rules→model→LLM→verify→receipt
│
├── rag/                  ← Retrieval-augmented generation (Gemini embeddings; FAISS, or numpy if FAISS can't load)
├── llm/                  ← LLM abstraction layer: adapter (Gemini · Groq · mock), versioned prompts, Pydantic schemas
│
├── models/scam_dl.npz    ← Shipped deep-model weights
├── data/
│   ├── scam_eval.csv, scam_heldout.csv, ordinary_text_eval.csv, scam_train_extra.csv  ← scam train/test data
│   ├── sample_sms.csv, sample_statement.csv       ← synthetic sample inputs
│   ├── chat_eval_{qa,social,adversarial}.csv      ← chat evaluation sets
│   ├── kb/               ← 92 knowledge-base docs: KB001–021 scam/safety advisories, KB022–066 finance education,
│   │                       KB067–092 money-book summaries & reading guides
│   ├── finance_kb/, build_*.py, fetch_*.py        ← generators / dataset fetchers
│   └── external/         ← downloaded datasets (git-ignored)
│
├── eval/                 ← quick_eval, run_eval, real_eval, chat_eval; results/ holds JSON, CSV, PNG
├── tests/                ← 219 tests incl. headless end-to-end UI tests
├── smoke_test.py         ← Checks your LLM key/model end to end
├── .env.example, requirements.txt
├── ARCHITECTURE.md, DEMO_SCRIPT.md
└── SPEC.md               ← Original product specification
```

## 🧪 Running tests

```bash
# Everything (219 tests: unit + headless Streamlit UI tests; no API key needed)
python -m pytest tests/ -v

# Without the UI tests (they need pandas, which some locked-down Windows machines block)
python -m pytest tests/ --ignore=tests/test_app_smoke.py

# End-to-end UI smoke test (runs the real app headlessly via streamlit.testing)
python -m pytest tests/test_app_smoke.py -v
```

FAISS is optional: if it cannot load (e.g. blocked DLL on some Windows machines), retrieval uses an exact numpy index.

## 📚 Data sources

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
| UCI SMS Spam Collection (Almeida & Hidalgo, 2011, CC BY 4.0) | Real ordinary SMS used as negative training/test examples |
| Own summaries (KB022–KB092) | Finance education + book summaries written in plain language; **pending human verification** |

Datasets (`scam_eval.csv`, `sample_sms.csv`, held-out sets) are **synthetic or hand-written** — clearly labelled in the files.

---

## ⚠️ Limitations & what it does NOT do

- ❌ No real money movement — educational tool only
- ❌ No live trading or NSE data; no bank account linking (SMS/CSV only — by design, for privacy)
- ❌ Ask Artha gives education, not advice: it will not recommend specific stocks, funds or crypto, or predict markets
- ❌ Ask Artha is English-only for now; very informal or multi-step messages may get "I'm not sure"
- ❌ Tax calculator skips surcharge (> ₹50 L), capital gains and senior-citizen slabs
- ❌ Link checker inspects the address only; it cannot see what a page contains
- ❌ Scam model trained mostly on synthetic and hand-written data — real-world accuracy may differ
- ❌ Unusual or bank-specific SMS formats may not parse correctly
- ❌ LLM calls add latency (~2–5 s) and free tiers are rate-limited — the app degrades gracefully without them
- ❌ Not a substitute for professional financial or legal advice

## 🛣️ Roadmap

Real Indian scam/Hinglish SMS data and a fresh held-out test set · Hindi/Hinglish chat (`core/lang.py` is ready) ·
multi-turn chat evaluation · human verification of KB022–KB092 · optional DistilBERT fine-tune distilled into the NumPy model.

---

## ⚖️ Disclaimer

Artha Kavach is an educational demonstration tool built for a hackathon. It does not provide financial, legal, or investment advice. Always verify suspicious messages with your bank directly or report them at [cybercrime.gov.in](https://cybercrime.gov.in) / helpline **1930**.

---

## 👥 Team

Built for Arthaton 2026 — *"AI for Finance"* — submission deadline 22 Nov 2026.
