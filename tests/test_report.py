"""Tests for the PDF money report (pure Python, no PDF library needed)."""

import csv
import re

from core.budget_engine import compute_budget
from core.categoriser import categorise_transactions
from core.insights import detect_subscriptions, weekly_spend
from core.parser import parse_messages
from core.report import _inr, build_monthly_report_pdf


def _sample():
    sms = [r["raw_sms"] for r in csv.DictReader(open("data/sample_sms.csv", encoding="utf-8")) if r["raw_sms"]]
    txns = categorise_transactions(parse_messages(sms))
    return compute_budget(txns), detect_subscriptions(txns), weekly_spend(txns)


def test_inr_uses_indian_grouping():
    assert _inr(115300) == "Rs 1,15,300"
    assert _inr(999) == "Rs 999"
    assert _inr(-47003) == "-Rs 47,003"
    assert _inr(1234567) == "Rs 12,34,567"


def test_pdf_is_structurally_valid():
    s, subs, weeks = _sample()
    pdf = build_monthly_report_pdf(s, subs, weeks)
    assert pdf.startswith(b"%PDF-1.4") and pdf.rstrip().endswith(b"%%EOF")
    # startxref must point at the xref table, and every xref entry at an object
    start = int(re.search(rb"startxref\n(\d+)", pdf).group(1))
    assert pdf[start:start + 4] == b"xref"
    offsets = [int(m) for m in re.findall(rb"(\d{10}) 00000 n", pdf)]
    for n, off in enumerate(offsets, 1):
        assert pdf[off:].startswith(f"{n} 0 obj".encode())
    assert pdf.count(b"/Type /Page ") == int(re.search(rb"/Count (\d+)", pdf).group(1))


def test_report_numbers_come_from_the_summary():
    s, subs, weeks = _sample()
    pdf = build_monthly_report_pdf(s, subs, weeks).decode("latin-1")
    assert _inr(s.total_income) in pdf and _inr(s.total_expense) in pdf
    assert "general information" in pdf          # disclaimer present
    assert "₹" not in pdf                    # no glyph the core fonts lack


def test_report_handles_minimal_inputs():
    s, _, _ = _sample()
    assert build_monthly_report_pdf(s).startswith(b"%PDF")            # no subscriptions / weeks
    assert build_monthly_report_pdf(s, [], []).startswith(b"%PDF")


def test_special_characters_do_not_break_pdf():
    s, subs, weeks = _sample()
    s.by_category = {"Café (₹ & \ ) stuff": 500.0, **s.by_category}
    pdf = build_monthly_report_pdf(s, subs, weeks)
    assert pdf.startswith(b"%PDF")
