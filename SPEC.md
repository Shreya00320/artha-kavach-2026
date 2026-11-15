\# ROLE

You are a senior full-stack + ML engineer and my pair-programmer. We are building a hackathon project that must be deployed, working end to end, and demo-ready within 7 days. Prioritise a small, reliable, well-tested product over a large, half-working one. Work in phases, run and test the code yourself after each phase, and tell me what you did and what is next.



\# THE HACKATHON

\- Name: Arthaton 2026. Theme: "AI for finance" for Indian users (UPI, bank SMS, NSE, tax, scams, small business).

\- Rules that matter: no real money, no live trading (historical data or paper trading only). Free entry, team of up to 3.

\- Submission deadline: 22 Nov 2026, 23:59 IST. We aim to submit the day before.

\- Judges (AI researchers, engineers, finance experts from Google, Perplexity, Mistral AI, Cadence, Bernstein, Elementary) score on: real-world impact, relevance to the theme, whether the app WORKS END TO END, use of AI, creativity/originality, and quality of the demo.

\- Therefore: a live link, one-click sample data, real evaluation numbers, and a tight 4-minute demo matter more than feature count.



\# THE PRODUCT: "Artha Kavach" (working name)

One-line pitch: "An AI money coach that protects you from UPI scams, builds your budget from bank SMS, and never says anything it can't prove."

Target user: students and first-job earners in India.

Core insight: finance apps fail because users cannot tell when the AI is wrong. We solve this with a "Trust Receipt": every AI explanation shows its sources, verified claims, and code-computed numbers. Research shows even the best LLM setups are unreliable on financial questions, so we verify before we speak.



Design principle (state this in the README): use plain code where code is reliable (arithmetic, parsing standard formats), a small classical model for cheap fast verdicts, and the LLM only where language understanding is needed (messy or Hinglish text, plain-language explanation, claim verification).



\# SCOPE (STRICT, DO NOT ADD FEATURES)

Build exactly three things:



\## Module 1: Scam Shield (primary feature)

Input: a pasted SMS / WhatsApp message / UPI collect-request description (English, Hindi, Hinglish).

Pipeline:

1\. Rules baseline: keyword and regex checks (urgency words, OTP/PIN requests, suspicious links, "collect request", KYC-expiry threats, lottery/prize, job-fee scams). Returns score + matched rules.

2\. Classical model: TF-IDF + logistic regression (scikit-learn) trained on our labelled dataset. Returns probability.

3\. LLM judge: receives the message, the rule hits, the classifier probability, and the top retrieved advisory passages. Returns STRICT JSON: {verdict: "scam"|"suspicious"|"safe", confidence: 0-1, red\_flags: \[{flag, quote\_from\_message, why\_it\_matters}], what\_to\_do: \[..], claims: \[{text, source\_id}]}.

4\. Claim verifier (second LLM call): for each claim, check it is supported by the cited passage. Mark "verified" / "unsupported". Drop or visibly flag unsupported claims.

5\. Output UI: verdict badge, red flags with the exact quoted text highlighted, plain-language advice, and the Trust Receipt panel (sources with titles/links, verified vs unverified claims, which of the three detectors agreed).

Rule: if the model is unsure, it says "not sure, treat with caution" rather than guessing.



\## Module 2: Smart Budget (supporting feature)

Input: pasted bank/UPI SMS messages, or a CSV, or the built-in sample dataset (one-click button).

Pipeline:

1\. Hybrid parser: regex templates for common bank formats first (amount, debit/credit, merchant/VPA, date, balance); LLM fallback with JSON-schema output for messages the regex cannot parse. Log which path was used.

2\. Categoriser: merchant lookup table first (Swiggy, Zomato, Uber, Amazon, rent, etc.); LLM fallback for unknown merchants; cache results.

3\. Budget engine (pure Python, unit-tested): monthly totals by category, 50/30/20 comparison, savings rate, recurring-payment detection, simple pace projection ("at this pace you will spend X by month end").

4\. Nudge writer: the LLM receives ONLY engine-computed numbers and writes 2-3 short, kind, specific nudges. It must never compute or invent numbers; any number in its text must appear in the engine output (add a post-check that rejects nudges containing numbers not in the engine data).

5\. Step-up savings chart: user enters income and a savings goal; a pure-code function compares "save a flat amount" vs "raise the savings share by 1-2 percentage points at each income increase", and plots both. Label it clearly as an illustration based on behavioural-finance research (Save More Tomorrow), not a guarantee.



\## Module 3: Trust Receipt (the thin layer that ties everything together)

A reusable component/service used by both modules that attaches: sources used, claims checked, verification status, which numbers were computed by code (show formula/inputs), and a confidence note. Keep it simple, visual and consistent.



\# EXPLICITLY OUT OF SCOPE (put on a "Roadmap" slide only)

Tax helper, investing/portfolio simulator, GST/small business, voice input, family accounts, real bank/Account Aggregator connections, login/accounts, mobile app, any trading, any stock recommendations.



\# SAFETY AND COMPLIANCE (non-negotiable)

\- Educational only. Never recommend specific stocks/funds, never give personalised "put X% in Y" instructions, never promise returns. Show a clear disclaimer in the UI and README.

\- No real user data. Use synthetic/sample data and user-pasted text processed in-session only; do not persist it. Mention privacy-by-design in the README.

\- Never fabricate statistics, citations, or sources. Every number in docs and slides must come from our own test results or a cited source. If a source is not in our knowledge base, say so.

\- Do not hard-code API keys. Use environment variables and a .env.example.

\- Never read, print, or modify the .env file.



\# TECH STACK

\- Language: Python 3.12 (Windows, PowerShell, venv at .venv)

\- UI: Streamlit

\- LLM: Gemini via the Google Gen AI SDK, behind a thin adapter class so the provider can be swapped in one file. Use structured/JSON output, temperature 0-0.2 for extraction and verification, retries with backoff, timeouts, and response caching to save cost and stay within free-tier rate limits.

\- Retrieval: sentence-transformers or the provider's embedding API + FAISS or Chroma (local, no external service). Small knowledge base (15-30 docs).

\- ML: scikit-learn. Testing: pytest. Deploy: Streamlit Community Cloud.

\- If a library is unavailable or the network is limited, tell me and propose a fallback instead of silently changing the design.



\# KNOWLEDGE BASE (for retrieval and citations)

Create /data/kb/ with 15-30 short documents, each with: id, title, publisher, URL, date accessed, and text excerpt. Topics: UPI/phishing/collect-request scam awareness, KYC and OTP fraud, fake job/prize/loan scams, "never share OTP/PIN" guidance, how to report (cybercrime portal and bank), basic budgeting and saving guidance. Use only official or reputable public sources (RBI, NPCI, government cybercrime sites, bank awareness pages). If you cannot fetch real sources in your environment, create the folder structure and a clearly marked TODO file listing the documents I must collect manually. NEVER invent a document or URL.



\# DATASETS

1\. /data/scam\_eval.csv: about 150 labelled messages (scam / suspicious / safe) in English, Hindi and Hinglish, including tricky legitimate bank alerts so we measure false positives. If you cannot source real public data, generate clearly labelled SYNTHETIC examples that mimic realistic patterns, and mark the file as synthetic in the README. Split 70/30 train/test with a fixed random seed. Include a tagged "hinglish" subset.

2\. /data/sample\_sms.csv: about 120 synthetic bank/UPI SMS messages across one month (several bank formats, some unparsable on purpose, Indian merchants, salary credit, rent, EMI, a couple of fraud-like entries).



\# EVALUATION (we must produce real numbers for the pitch)

Write /eval/run\_eval.py that outputs a results table and saves charts:

1\. Scam detection on the held-out test set: precision, recall, F1, confusion matrix for (a) rules baseline, (b) TF-IDF+LR, (c) LLM judge, (d) the combined pipeline. Report the Hinglish subset separately.

2\. Grounding comparison: 20-30 finance Q\&A prompts answered (a) without retrieval, (b) with retrieval + verification. Provide a CSV template for me to hand-score correctness against sources, plus a script to summarise scores.

3\. Parser: parse success rate for regex-only vs regex+LLM fallback on sample\_sms.csv.

4\. Engine unit tests: budget totals, step-up savings, recurring detection, number-check on nudges (all must pass).

Be honest: report small-sample limitations in the output and the README. Include 2-3 real failure cases with explanations.



\# SUGGESTED STRUCTURE

/app (UI), /core (parser.py, categoriser.py, budget\_engine.py, savings.py, nudges.py), /scam (rules.py, classifier.py, llm\_judge.py, verifier.py, pipeline.py), /rag (ingest.py, retrieve.py), /llm (adapter.py, prompts.py, schemas.py), /data, /eval, /tests, README.md, ARCHITECTURE.md, .env.example, requirements.txt.



\# PROMPTS

Put every LLM prompt in /llm/prompts.py as named constants with versioning. Each must: define the task and schema, forbid inventing facts or numbers, require "unsure" when evidence is weak, and require JSON only. Add schema validation (pydantic) and a repair-retry on malformed JSON.



\# BUILD PLAN (work phase by phase; after each phase run tests, show results, and wait for my "continue" only if something is ambiguous)

Phase 0: Confirm stack and assumptions with me (max 5 short questions), then scaffold the repo and the LLM adapter, with a smoke test.

Phase 1: Data files, SMS parser, categoriser, budget engine, savings function, and unit tests.

Phase 2: Knowledge base ingestion and retrieval with citations.

Phase 3: Scam Shield (rules, classifier, LLM judge, verifier, pipeline) and the Trust Receipt component.

Phase 4: UI with three screens (Scam Shield, Smart Budget, About/How it works), one-click sample data, loading states, error states, and a clean readable design.

Phase 5: Evaluation scripts, run them, fix the worst failures, and record the numbers.

Phase 6: Deployment, a live-link checklist, a README with screenshots and setup, ARCHITECTURE.md with a diagram, and a pitch outline plus a 4-minute demo script.

Freeze features after Phase 5. After that, only bug fixes.



\# DEFINITION OF DONE

\- A judge opens the live link and, with zero setup, can: load sample data, see a categorised budget with nudges, paste a scam message and get a verdict with explained red flags and a verified-source Trust Receipt.

\- All tests pass; eval numbers exist; no secrets in the repo; a graceful message appears if the LLM API fails (fall back to rules + classifier so the demo never breaks).

\- README states what it does NOT do, the data sources, the limitations, and the disclaimer.



\# HOW TO WORK WITH ME

\- Be concise. At the end of each phase give: what was built, how to run it, test results, known issues, and the next step.

\- If something is risky for the deadline, say so and propose the smaller option.

\- Ask before changing scope. Never silently skip a requirement; tell me what you skipped and why.

\- Wait for my instruction before starting each new phase.

