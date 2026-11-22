# 🎬 Artha Kavach — Q&A
## Arthaton 2026 · AI for Finance

---

 Q&A —

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
