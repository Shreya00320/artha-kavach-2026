## Knowledge Base — TODO / Manual Verification Required

This file lists KB documents that need manual URL verification or content
expansion before final submission. The documents exist in `data/kb/` with
accurate content based on official public guidance, but specific page URLs
should be verified by visiting the publisher's website.

---

### Documents to verify exact URLs

| ID | Title | Publisher | Verify at |
|---|---|---|---|
| KB002 | RBI Fraud Advisory | RBI | rbi.org.in → Consumer Education |
| KB004 | KYC Fraud | RBI | rbi.org.in → Be(a)Ware booklet |
| KB009 | Fake Loan Scam | RBI | rbi.org.in → Press Releases |
| KB011 | 50/30/20 Rule | RBI Financial Literacy | rbi.org.in → Financial Education |
| KB013 | Emergency Fund | RBI Financial Literacy | rbi.org.in → Financial Education |

### Documents that could benefit from additional text

- **KB001**: Add NPCI's specific UPI dispute resolution process
- **KB003**: Add step-by-step cybercrime.gov.in complaint filing UI walkthrough
- **KB008**: Add CERT-In's specific list of known phishing domains (updated list)
- **KB015**: Add SEBI's current list of verified investment advisors

### Additional documents to consider adding (Phase 5+)

- RBI Banking Ombudsman process (bankingombudsman.rbi.org.in)
- NPCI's official UPI dispute escalation timeline
- TRAI regulations on commercial SMS (DLT registered SMS vs scam)
- Income Tax Refund process — official flow to prevent refund scams
- Aadhaar OTP usage guidelines (uidai.gov.in)

### Note on synthetic content

All KB documents contain accurate summaries of real public guidance.
They are marked `synthetic` only in the sense that the text was
composed from known official positions, not copied verbatim from a
specific URL. No facts have been invented.

**NEVER add a KB document with an invented URL or unverified statistic.**

---

## KB022–KB066 (finance education set, added 2026-11-18) — NEEDS HUMAN VERIFICATION

These 45 entries are Artha Kavach's own plain-language summaries written from general
knowledge of RBI / SEBI / IRDAI / Income Tax Dept public guidance. They are marked
`"verified": false` and the publisher field says "pending manual verification".
Re-check against official sources before any public launch, especially:

- Interest rates (PPF ~7.1%, EPF ~8%+, FD 6–7.5%, savings 2.5–4%, SSY/SCSS) — these reset; verify current.
- Tax: new-regime slabs, ₹75,000 standard deduction, 87A rebate to ₹12 lakh (matches core/tax.py),
  80C ₹1.5L, 80CCD(1B) ₹50k, 80D limits, 80TTA ₹10k, 24(b) ₹2L, 80E, crypto 30% + 1% TDS, TDS thresholds.
- SEBI F&O study figure ("around nine in ten lose money") — confirm latest SEBI report wording.
- DICGC cover ₹5 lakh; RTGS minimum ₹2 lakh; RBI digital-lending rules (KFS, cooling-off, direct disbursal).
- SGB: statement that the government has stopped new issuances.
- Credit-card interest 3–4%/month; home-loan LTV 75–90%; ULIP taxation note.
- Gratuity formula (15/26 × last basic × years) summarised as "15 days per year".

Regenerate the JSON from `data/finance_kb/*.py` with `python data/build_finance_kb.py`.

---

## KB067-KB092 (money-book summaries, added 2026-11-18) — NEEDS HUMAN VERIFICATION

Original paraphrased summaries of 22 well-known money books plus 4 meta entries (reading list,
where books agree/disagree, how to read them critically). No text is quoted from the books.
Verify before launch: author names and publication years, the claims attributed to each book
(especially KB078 Let's Talk Money, KB086 The Joys of Compounding, KB087 Stocks to Riches, and the
percentages in KB071 and KB083), and the criticisms listed (KB069, KB075, KB077). The `url` fields
are Open Library search links, not publisher pages.


---

## Verification log — 2026-11-20 (done by Claude with web searches; primary documents mostly NOT fetched)

Each KB JSON now has `verified_claims`, `unverified_claims`, `sources`, `last_checked`. `verified: true` only if `unverified_claims` is empty.

| Entry | Checked | Result | How strong |
|---|---|---|---|
| KB025 PPF | rate for Oct–Dec 2026 | 7.1%, unchanged | DEA notification via Business Today, FPJ, Angel One, taxguru copy (ministry page not fetched) |
| KB026 EPF | FY 2025-26 rate | 8.25%, ratified June 2026 | several news reports; EPFO notice not fetched |
| KB038 FD / DICGC / TDS | DICGC cover; TDS on bank interest | ₹5 lakh (official DICGC FAQ); ₹50,000 / ₹1 lakh seniors from 1 Apr 2025 | DICGC official; TDS from Finance Bill extract + reports (one report said 1 Apr 2026 for seniors — outlier) |
| KB042 Gold / SGB | issuance status | no new tranche since Feb 2024; reports differ on "paused" vs "discontinued" | secondary only |
| KB044 F&O | SEBI study | 91% of individual F&O traders lost money in FY25, ₹1.05 lakh crore | news reports of SEBI's 7 Jul 2025 study; a newer FY26 study exists, unchecked |
| KB045 Crypto | Budget 2026 | 30% tax and 1% TDS unchanged | several reports; exact TDS thresholds conflict, text avoids them |
| KB065 Small savings | Oct–Dec 2026 rates | PPF 7.1, SSY 8.2, SCSS 8.2, NSC 7.7, POMIS 7.4, 5-yr RD 6.7 | as KB025 |
| KB029 Regime choice | slabs, rebate | unchanged for FY 2026-27 (secondary); **old rule of thumb was WRONG** and was replaced with computed break-evens | calculator + hand algebra |
| KB030 HRA | metro list | eight cities at 50% from FY 2026-27 per Income-tax Rules 2026 — sources disagree whether final | secondary only; **confirm with CBDT notification** |
| KB094 Capital gains (new) | STCG 20%, LTCG 12.5% over ₹1.25 lakh, 12-month rule, unchanged Budget 2026-27 | several explainers + Business Standard | secondary |

Still to do by a human: fetch the primary notices (DEA small-savings, EPFO, CBDT HRA rule, Finance Act 2025/2026 text), check the 80D/80TTA limits,
the EPF ₹2.5 lakh taxable-interest threshold, gratuity (15/26 × basic × years, ₹20 lakh limit), RTGS/IMPS limits, and the 25 book summaries (KB067–KB089).
UPI per-transaction limits were checked (P2P ₹1 lakh/day unchanged; ₹5 lakh per transaction for capital-markets/insurance merchants from 15 Sep 2025) but
KB058 only says limits exist, so nothing was changed.
