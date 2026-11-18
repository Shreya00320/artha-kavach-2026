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
