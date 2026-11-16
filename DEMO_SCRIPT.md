# 🎬 Artha Kavach — 4-Minute Demo Script
## Arthaton 2026 · AI for Finance

---

## PRE-DEMO CHECKLIST (5 min before)

- [ ] App open at the live URL (or `streamlit run app/main.py` running locally)
- [ ] Sidebar shows: ✅ LLM — Live (Gemini) | ✅ KB — Loaded | ✅ ML Classifier — Trained
- [ ] Tab 1 (Scam Shield) is active
- [ ] Browser font size bumped up (~125%) so text is readable on screen
- [ ] `.env` has valid `GEMINI_API_KEY`

---

## SCRIPT

### ⏱️ 0:00–0:30 — Hook (30 sec)

> "India processed over 14 billion UPI transactions last year. And scammers know this.
> Every 10 minutes, someone in India loses money to a fake collect request or a phishing SMS.
>
> The problem isn't that people are careless — it's that **they can't tell when the AI is wrong**.
> Most apps just say 'this looks suspicious'. No source. No explanation. Just vibes.
>
> We built Artha Kavach — an AI money coach that **protects you from UPI scams, builds your budget from bank SMS, and never says anything it can't prove**."

---

### ⏱️ 0:30–1:45 — Scam Shield demo (75 sec)

**[Click "📋 Load a sample message" → select "🚨 OTP phishing (Hinglish)"]**

> "Let's start with something real. This is a Hinglish scam SMS — the kind millions of people get every day."

**[Click "Load sample"]**  
Message appears:
> *"Aapka SBI account block ho jayega. Abhi apna OTP 7382 share karo ya yahan click karo: http://sbi-kyc.update.click/verify"*

**[Click "🔍 Analyse message"]**

> "Three things are running in parallel right now:
> a rules engine checking for OTP requests and phishing links,
> a machine-learning classifier trained on 155 labelled SMS messages,
> and a Gemini-powered judge that reads official RBI and NPCI advisories to build its case."

🚨 **SCAM badge appears**

> "Scam — 85% confidence. But look at what's different about this."

**[Point to the highlighted text in the message]**
> "The exact suspicious words are highlighted right inside the original message. No vague summary."

**[Scroll down — point to "What to do"]**
> "Plain-English advice — in the same language as the message."

**[Click "🔍 Trust Receipt"]**
> "And here's what makes Artha Kavach different from every other scam detector.
> This is the **Trust Receipt**. It shows:
> - which three detectors agreed — rules, ML, and LLM all voted scam
> - the exact RBI and NPCI advisory passages it used as evidence
> - each claim the AI made — individually verified against those passages.
>
> The AI literally cannot bluff its sources. We check."

---

### ⏱️ 1:45–2:45 — Smart Budget demo (60 sec)

**[Click "💰 Smart Budget" tab]**  
**[Click "🎲 Sample data" → "▶ Load sample dataset"]**

> "Now let's flip to the budget side. I'm loading 120 synthetic bank SMS messages — SBI, HDFC, ICICI, Paytm — all from one month."

*Spinner runs → results appear*

> "In under two seconds: ₹70,300 income, ₹1,12,818 expenses — yes, this person is overspending, which is exactly the kind of insight a first-job earner needs."

**[Point to 50/30/20 chart]**
> "The 50/30/20 breakdown shows Wants are ₹15,000 over budget."

**[Point to nudges]**
> "These nudges were written by Gemini — but every single number in them came from Python code. The AI is not allowed to do arithmetic. We post-check every nudge and reject it if it invents a number. Trust, by design."

**[Scroll to savings planner]**
> "And a savings planner — flat savings versus the Save More Tomorrow strategy from behavioural finance research. Clearly labelled as an illustration, not a guarantee."

---

### ⏱️ 2:45–3:30 — Architecture & numbers (45 sec)

**[Click "📖 About" tab, or switch to a slide]**

> "Here's the design principle we're proud of:
>
> **Code where code is reliable. Small ML for fast verdicts. LLM only for language.**
>
> Every budget number is computed by Python — auditable, deterministic, zero hallucination risk.
> Every scam verdict carries a Trust Receipt — sources, verified claims, detector votes.
>
> The numbers:"

| | |
|--|--|
| ML Classifier macro-F1 | **0.72** |
| Scam class F1 | **0.80** |
| Hinglish ML score | **0.82** |
| Parser amount accuracy | **100%** |
| Unit tests passing | **72 / 72** |

> "And critically — the app never breaks. No API key? It falls back to rules plus ML.
> LLM fails mid-demo? The fallback kicks in silently. The judges will always see a working product."

---

### ⏱️ 3:30–4:00 — Close (30 sec)

> "Artha Kavach is live at [URL] — no account, no setup. Load sample data, paste a scam, see the Trust Receipt.
>
> The judges from Google, Perplexity, Bernstein, and Mistral care about two things:
> does it work end to end, and does it have real impact.
>
> We have both. Working app, real eval numbers, honest caveats, and a design that explains itself.
>
> Thank you."

---

## BACKUP — if live URL fails

```bash
cd C:\Users\DELL\Documents\AI-FINANCE
.venv\Scripts\streamlit.exe run app/main.py
# Opens at http://localhost:8501
```

## BACKUP — if LLM is down

The app automatically falls back to rules + ML. The verdict badge still appears.
Say: *"The LLM is offline but the demo keeps running — that's the graceful degradation we built in."*

## BACKUP SCAM MESSAGES (paste manually if sample data fails)

**Strong scam (all detectors agree):**
```
URGENT: Your KYC is expiring! Share OTP 7382 now or account blocked in 2 hours. Click: http://sbi-kyc.update.click/verify
```

**Safe bank SMS (should score low):**
```
Rs 1,250.00 debited from A/c XX4521 on 14-Nov-26 at SWIGGY. Avl Bal: Rs 12,340.50 —SBI
```

**Hinglish scam:**
```
Aapka SBI account block ho jayega. Abhi apna OTP 7382 share karo ya yahan click karo: http://sbi-kyc.update.click/verify
```

---

## LIKELY JUDGE QUESTIONS

**Q: What if someone submits a totally new type of scam the model hasn't seen?**
> "The rules engine and classifier will likely miss it — that's exactly why the LLM judge exists. It reads the message fresh with KB context, not from a lookup table. And the Trust Receipt shows the confidence level, so the user knows when to be extra careful."

**Q: Why not just use an LLM for everything?**
> "Three reasons: cost, latency, and reliability. The rules engine and classifier handle 80% of cases instantly, offline, for free. The LLM adds value at the edges. And for budget numbers, letting an LLM do arithmetic is a known failure mode — we proved this matters by running the nudge number-check."

**Q: The dataset is synthetic — does it generalise?**
> "Honestly, we don't know yet — that's in the README. The eval numbers are directional. The real validation would be a field study with actual SMS data from consenting users. We designed the pipeline so each component (rules, ML, LLM) can be improved independently as more data arrives."

**Q: What's the business model?**
> "Free tier covers offline rules + ML. Premium unlocks the LLM judge and KB retrieval — pay-as-you-go on API cost, with disk caching to minimise spend. Target: partner with NPCI or a fintech for data and distribution."
