# 🎬 Artha Kavach — 3-Minute Demo Script + Judge Q&A
## Arthaton 2026 · AI for Finance

---

## Pre-demo checklist (10 min before)

- [ ] Live app opens **without sign-in** (Streamlit Cloud → Settings → Sharing → public)
- [ ] Sidebar shows ✅ LLM — Live (Groq · openai/gpt-oss-120b, or Gemini) · ✅ Knowledge base — Loaded (21 docs, local retriever on Groq) · ✅ Deep scam model — Trained
- [ ] Secrets: Groq → `LLM_PROVIDER=groq`, `GROQ_API_KEY`, `LLM_MODEL=openai/gpt-oss-120b`; Gemini → `LLM_MODEL=gemini-3.8-flash`, `EMBEDDING_MODEL=gemini-embedding-001`
- [ ] `python smoke_test.py` passes (the free Groq tier is rate-limited: avoid rapid-fire clicking; cached repeats are instant)
- [ ] Ran the 🧠 "papa on a new number" sample once today (warms the LLM cache, confirms the key works)
- [ ] Browser zoom ~125%; close other tabs; phone on silent
- [ ] Backup: `streamlit run app/main.py` on a laptop — the app works **without internet** (rules + ML)

> ⚠️ Only quote statistics you can source on a slide (e.g. NPCI monthly UPI volumes, I4C/MHA fraud
> figures). An unsourced number undermines a product whose pitch is "never says what it can't prove".

---

## The story (3:00)

### 0:00–0:25 — Hook
> "Meet Priya, 22, first job. Yesterday a 'Mumbai Cyber Crime inspector' video-called her: a parcel in
> her name had drugs, she was under 'digital arrest', and she had to transfer ₹25,000 to 'verify her funds'.
> She paid. Today she wants to know: was it a scam, what now, and can she still pay rent?
> Artha Kavach answers all three — and never says a number it can't prove."

**[Sidebar → 🎬 Load demo story]**

### 0:25–1:10 — Scam Shield
**[🛡️ Scam Shield → 🔍 Analyse message]**
> "Red verdict in under a second. Look at the strip: rules, ML model and the AI judge each voted —
> you see who said what. Red flags are quoted word-for-word from the message, and the UPI ID and links are
> checked without ever opening them."

**[Open 🔍 Trust Receipt]**
> "Every claim the AI makes cites an official source — I4C, RBI — and a second AI call verifies the
> claim against that source. Unverified claims are dropped. The AI can't bluff."

### 1:10–1:40 — 🆘 I've been scammed
**[Click 🆘 I've been scammed]**
> "Priya already paid. Step one: call 1930 — inside the golden hour the money can still be frozen.
> Then her bank — under RBI's 2017 rules, reporting within 3 working days matters.
> She fills five fields and gets a complaint ready to paste into cybercrime.gov.in.
> (If asked: Scam Shield also names the tactic used, like 'fake authority', so users learn to spot it.)"

### 1:40–2:20 — Smart Budget
**[💰 Smart Budget → 🔔 Alerts]**
> "Her month, built from bank SMS — no bank login, nothing stored. The ₹25,000 to an unknown UPI ID is flagged.
> Money to friends isn't counted as spending, refunds are netted, subscriptions add up to a yearly figure.
> Every number here is plain Python — the AI never does arithmetic. It even shows her biggest 'want' as hours of work."

### 2:20–2:45 — Ask Artha
**[💬 Ask Artha → type "Can I afford ₹9,000 for rent?"]**
> "She can just ask — about her own month, or money basics: try "What is a SIP?" or "Which money books should a beginner read?" (answered from our 93-document knowledge base, with sources). Ask for a stock tip and it refuses. The AI phrases the answer, but if it writes any number our code didn't compute,
> the reply is thrown away and replaced. That's our rule everywhere: never say a number you can't prove."

### 2:45–3:00 — Close
> "Scam check, a plan when it's too late, and a budget that tells the truth — in English, Hindi and Hinglish,
> working even offline. Artha Kavach."

**If time allows:** 🛡️ → 🧠 "papa on a new number" sample — rules say *safe*, the AI judge catches it.

---

## Judge Q&A — every team member should be able to answer

**Q: Where is the AI? Isn't this mostly rules?**
Three layers on purpose: rules (fast, explainable, offline), a small neural network (hashed word + character
n-gram embeddings, ~5 MB, NumPy-only inference — catches patterns rules miss, handles Hinglish spelling), and an LLM judge
with retrieval over our official advisories for messages that need understanding (the "papa" example).
A second LLM call verifies each claim. We use the LLM only where language understanding is needed.

**Q: How do you combine the detectors?**
Rules use noisy-OR: score = 1 − ∏(1 − weightᵢ), so independent weak signals add up. Offline, the more severe
of the rules verdict and the classifier verdict wins — missing a scam costs far more than a false alarm.
With an API key, the LLM judge sees the message, the rule hits, the classifier probabilities and the
retrieved advisories, and gives the final verdict.

**Q: How do you stop the AI from hallucinating numbers?**
All arithmetic is Python. The LLM only receives computed facts, and a post-check extracts every number in
its reply; any number not in the facts (±1% rounding) rejects the reply and we fall back to a rules answer.
Same for budget nudges.

**Q: How accurate is it?**
On our 47-message held-out test set (synthetic): offline macro F1 0.77; rules alone flag no safe messages.
The deep model gives 2% false alarms on 300 real everyday SMS it never trained on, and catches 97% of 38 new hand-written
scams (77% exactly labelled "scam"). Ask Artha: 99% right source on 168 finance questions, 100% on 42 adversarial ones, 0 unbacked numbers.
The SMS parser reads all 91 transaction SMS in our sample. Caveat: synthetic data — [add your real-SMS result
here: `python -m eval.real_eval data/private/real_sms.csv`].

**Q: Which LLM do you use, and is the app dependent on it?**
Gemini or Groq (free, `openai/gpt-oss-120b`), switchable with one env var. The scam model, budget, tax, goals, PDF report and the
chat's knowledge base all run locally — the LLM is only for judging subtle messages, verifying claims and phrasing.

**Q: Can Ask Artha tell me which stock or fund to buy?**
No — by design. It refuses stock/fund/crypto picks and market predictions, explains concepts from the knowledge base, warns about
"guaranteed return" pitches, and says "I'm not sure" when retrieval is weak.

**Q: Would anyone really paste SMS?**
Today: paste or CSV, so no bank credentials and no SMS permission. Roadmap: Android on-device SMS reading
(iOS doesn't allow it). Bank-statement CSV import already works today. Privacy is the reason we didn't start with bank linking.

**Q: Privacy?**
Data lives in the session only; a sidebar button wipes it. Offline mode sends nothing anywhere. With a key,
message text goes to the LLM provider for analysis — we say so in the app.

**Q: What if a scam uses a new pattern?**
The classifier and LLM generalise beyond rules; the link checker catches lookalike domains by edit distance.
New rules and advisories are one-line additions, and every verdict says which detector fired.

**Q: Is the tax calculator correct?**
FY 2026-27 slabs (unchanged by Budget 2026), 87A rebate with marginal relief, deduction caps — unit-tested
against hand calculations. It states what it doesn't cover (surcharge, capital gains, senior slabs).

**Q: Business model / next steps?**
Free for individuals; partnerships with banks/colleges for financial-literacy and fraud-awareness programmes;
an on-device Android version; Hindi UI; real-world labelled data from opted-in users.
