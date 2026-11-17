"""
tests/test_features.py — Tests for the one-stop features:
parser formats, categoriser (P2P / refunds / UPI handles / word matching),
budget engine transfers & refunds, insights, tax, goals, assistant,
link checker, emergency kit and the new scam rules.

All offline — no API key, no FAISS, no pandas.
"""

from datetime import date

import pytest

from core.parser import parse_message, ParsedTransaction
from core.categoriser import (
    categorise, categorise_transactions, CategorisedTransaction,
    looks_like_person, resolve_merchant, _lookup, _CACHE,
)
from core.budget_engine import compute_budget, compute_pace


def _txn(merchant, amount, ttype, category, d, vpa=None, raw=""):
    return CategorisedTransaction(
        id=f"T{abs(hash((merchant, amount, d))) % 10**6}", raw_message=raw or f"{merchant} {amount}",
        amount=amount, transaction_type=ttype, merchant=merchant, vpa=vpa, date=d,
        balance=None, bank="SBI", parse_method="regex", confidence=0.9,
        category=category, category_method="lookup", category_confidence=1.0,
    )


@pytest.fixture(autouse=True)
def _clear_cache():
    _CACHE.clear()
    yield
    _CACHE.clear()


# ---------------------------------------------------------------------------
# Parser — formats not present in the sample dataset
# ---------------------------------------------------------------------------

class TestParserFormats:
    @pytest.mark.parametrize("sms,amount,ttype,merchant,d", [
        ("Rs 649.00 debited from A/c XX2341 on 03-Nov-26. Info: HOTSTAR PREMIUM. Avl Bal: Rs 7,151.00 —ICICI",
         649.0, "debit", "HOTSTAR PREMIUM", "2026-11-03"),
        ("Your A/c XX8810 is debited Rs 3,200.00 on 05-Nov-26 for EMI-HDFC PERSONAL LOAN. Avl Bal Rs 15,000.00",
         3200.0, "debit", "EMI-HDFC PERSONAL LOAN", "2026-11-05"),
        ("Dear UPI user A/C X1234 debited by Rs.250.00 on date 14Nov26 trf to SWIGGY Refno 431234567890. If not u? call 1800",
         250.0, "debit", "SWIGGY", "2026-11-14"),
        ("INR 1,499.00 credited to your A/c XX9911 on 12/11/2026. Info: AMAZON REFUND. Avl Bal: INR 9,120.00",
         1499.0, "credit", "AMAZON REFUND", "2026-11-12"),
        ("Paid Rs 120 to Chai Point via UPI on 15-Nov-2026. UPI Ref 998877",
         120.0, "debit", "Chai Point", "2026-11-15"),
    ])
    def test_generic_formats(self, sms, amount, ttype, merchant, d):
        p = parse_message(sms)
        assert p.parse_method == "regex"
        assert p.amount == amount
        assert p.transaction_type == ttype
        assert p.merchant == merchant
        assert p.date == d

    def test_otp_message_not_parsed_as_transaction(self):
        p = parse_message("Your OTP for login is 482913. Do not share it with anyone. —HDFC Bank")
        assert p.parse_method == "failed"

    def test_balance_alert_not_parsed(self):
        assert parse_message("Bank maintenance scheduled tonight. —SBI").parse_method == "failed"


# ---------------------------------------------------------------------------
# Categoriser
# ---------------------------------------------------------------------------

class TestCategoriser:
    def test_word_boundary_no_false_emi(self):
        # "PREMIUM" contains "emi", "PARENT" contains "rent" — must not match
        assert _lookup("ACKO PREMIUM") == "Savings_Investment"
        assert _lookup("GIFT FOR PARENTS") is None
        assert _lookup("COCA-COLA VENDING") is None   # not "ola"

    def test_longest_match_wins(self):
        assert _lookup("HOTSTAR PREMIUM") == "Entertainment"
        assert _lookup("EMI-HDFC LOAN") == "EMI_Loan"

    def test_person_vpa_is_transfer(self):
        assert looks_like_person("rahul.kumar", "rahul.kumar@oksbi")
        assert looks_like_person(None, "9876543210@ybl")
        assert not looks_like_person("swiggy.stores", "swiggy.stores@axb")
        assert not looks_like_person("autorickshaw", "autorickshaw@ybl")

    def test_vpa_brand_resolution(self):
        assert resolve_merchant("zomato-order", "zomato-order@paytm") == "Zomato"
        assert resolve_merchant("rzp", "razorpay.abc123@icici") == "Razorpay merchant"
        assert resolve_merchant("mama", "mama@upi") == "mama"

    def test_p2p_sent_categorised_transfer(self):
        p = parse_message("Sent Rs 500.00 to rahul.kumar@oksbi via UPI on 02-Nov-26. UPI Ref: 123456789012. —PhonePe")
        assert categorise(p).category == "Transfer"

    def test_refund_credit(self):
        p = parse_message("INR 1,499.00 credited to your A/c XX9911 on 12/11/2026. Info: AMAZON REFUND. Avl Bal: INR 9,120.00")
        assert categorise(p).category == "Refund"

    def test_salary_keyword_without_merchant(self):
        p = parse_message("Rs 45,000.00 credited to A/c XX5566 on 01-Nov-26. NEFT SALARY-INFOSYS. Avl Bal: Rs 50,000.00 —SBI")
        assert categorise(p).category == "Salary"


# ---------------------------------------------------------------------------
# Budget engine: transfers excluded, refunds netted, pace reference
# ---------------------------------------------------------------------------

class TestBudgetTransfersRefunds:
    def _txns(self):
        return [
            _txn("Salary", 40000, "credit", "Salary", "2026-10-01"),
            _txn("Amazon", 3000, "debit", "Shopping", "2026-10-03"),
            _txn("Amazon refund", 1000, "credit", "Refund", "2026-10-06"),
            _txn("rahul.kumar", 2000, "debit", "Transfer", "2026-10-07"),
            _txn("anita", 500, "credit", "Transfer", "2026-10-08"),
            _txn("Swiggy", 1500, "debit", "Food", "2026-10-10"),
        ]

    def test_transfers_excluded_and_refunds_netted(self):
        s = compute_budget(self._txns())
        assert s.total_expense == 3000 - 1000 + 1500
        assert s.transfers_out == 2000
        assert s.transfers_in == 500
        assert s.refunds_total == 1000
        assert s.total_income == 40000           # transfers in are not income
        assert sum(s.by_category.values()) == pytest.approx(s.total_expense)

    def test_transfers_can_be_included(self):
        s = compute_budget(self._txns(), exclude_transfers=False)
        assert s.total_expense == 3000 - 1000 + 1500 + 2000

    def test_pace_uses_latest_month_in_data(self):
        pace = compute_pace(self._txns())  # data is Oct 2026, "today" is later
        assert pace["current_month"] == "2026-10"
        assert pace["current_month_spend"] == 4500   # transfers excluded, refunds are credits
        assert pace["reference_date"] == "2026-10-10"


# ---------------------------------------------------------------------------
# Insights
# ---------------------------------------------------------------------------

class TestInsights:
    def test_subscriptions_known_and_recurring(self):
        from core.insights import detect_subscriptions
        txns = [
            _txn("NETFLIX", 649, "debit", "Entertainment", "2026-10-03"),
            _txn("GYM BUDDY", 1200, "debit", "Healthcare", "2026-09-05"),
            _txn("GYM BUDDY", 1200, "debit", "Healthcare", "2026-10-05"),
            _txn("Amazon", 3000, "debit", "Shopping", "2026-10-03"),
            _txn("Amazon", 450, "debit", "Shopping", "2026-09-03"),   # varying amount → not a sub
        ]
        subs = {s.merchant.lower(): s for s in detect_subscriptions(txns)}
        assert "netflix" in subs and subs["netflix"].annual_cost == 649 * 12
        assert "gym buddy" in subs and subs["gym buddy"].source == "recurring"
        assert "amazon" not in subs

    def test_anomaly_flags_outlier_only(self):
        from core.insights import detect_anomalies
        txns = [_txn("Swiggy", a, "debit", "Food", f"2026-10-{i + 1:02d}") for i, a in enumerate([300, 350, 280, 320, 2400])]
        flagged = detect_anomalies(txns)
        assert [a.amount for a in flagged] == [2400]

    def test_small_spend_summary(self):
        from core.insights import small_spend_summary
        txns = [_txn("Chai", 20, "debit", "Food", "2026-10-01"), _txn("Auto", 60, "debit", "Transport", "2026-10-01"),
                _txn("Rent", 9000, "debit", "Rent", "2026-10-02")]
        s = small_spend_summary(txns, threshold=100)
        assert s["count"] == 2 and s["total"] == 80

    @pytest.mark.parametrize("start_day,ref,exp_start,exp_end", [
        (1, date(2026, 11, 17), date(2026, 11, 1), date(2026, 11, 30)),
        (27, date(2026, 11, 17), date(2026, 10, 27), date(2026, 11, 26)),
        (27, date(2026, 11, 28), date(2026, 11, 27), date(2026, 12, 26)),
        (31, date(2027, 2, 15), date(2027, 1, 31), date(2027, 2, 27)),
        (5, date(2027, 1, 2), date(2026, 12, 5), date(2027, 1, 4)),
    ])
    def test_cycle_bounds(self, start_day, ref, exp_start, exp_end):
        from core.insights import cycle_bounds
        assert cycle_bounds(start_day, ref) == (exp_start, exp_end)

    def test_tax_tags(self):
        from core.insights import tax_tags
        tags = tax_tags([_txn("LIC PREMIUM", 2500, "debit", "Savings_Investment", "2026-10-01"),
                         _txn("STAR HEALTH", 8000, "debit", "Savings_Investment", "2026-10-02"),
                         _txn("NPS CONTRIBUTION", 5000, "debit", "Savings_Investment", "2026-10-03")])
        assert len(tags["80C"]) == 1 and len(tags["80D"]) == 1 and len(tags["80CCD(1B)"]) == 1

    def test_csv_export_roundtrip(self):
        import csv, io
        from core.insights import transactions_to_rows, rows_to_csv
        out = rows_to_csv(transactions_to_rows([_txn("Swiggy", 300, "debit", "Food", "2026-10-01")]))
        rows = list(csv.DictReader(io.StringIO(out)))
        assert rows[0]["merchant"] == "Swiggy" and rows[0]["category"] == "Food"


# ---------------------------------------------------------------------------
# Tax (FY 2026-27) — expected values worked out by hand
# ---------------------------------------------------------------------------

class TestTax:
    def test_new_regime_zero_tax_up_to_12_75_lakh_salary(self):
        from core.tax import compute_tax
        r = compute_tax(1_275_000, "new")
        assert r.taxable_income == 1_200_000
        assert r.tax_on_slabs == 60_000
        assert r.total_tax == 0

    def test_new_regime_16_lakh(self):
        from core.tax import compute_tax
        # taxable 15,25,000: 20,000 + 40,000 + 15% of 3,25,000 (48,750) = 1,08,750 + 4% cess
        r = compute_tax(1_600_000, "new")
        assert r.tax_on_slabs == 108_750
        assert r.total_tax == 113_100

    def test_marginal_relief_just_above_12_lakh(self):
        from core.tax import compute_tax
        # taxable 12,10,000 → slab tax 61,500, but tax may not exceed the 10,000 above 12 L
        r = compute_tax(1_285_000, "new")
        assert r.taxable_income == 1_210_000
        assert r.tax_after_rebate == 10_000
        assert r.total_tax == 10_400

    def test_old_regime_with_80c(self):
        from core.tax import compute_tax, Deductions
        # 10,00,000 - 50,000 std - 1,50,000 80C = 8,00,000 → 12,500 + 60,000 = 72,500 + cess
        r = compute_tax(1_000_000, "old", Deductions(sec_80c=200_000))
        assert r.taxable_income == 800_000
        assert r.total_tax == 75_400

    def test_old_regime_rebate_up_to_5_lakh(self):
        from core.tax import compute_tax
        assert compute_tax(550_000, "old").total_tax == 0   # taxable 5,00,000

    def test_caps(self):
        from core.tax import Deductions
        a = Deductions(sec_80c=500_000, sec_80d_self=90_000, sec_80d_parents=90_000,
                       parents_senior=True, sec_80ccd1b=90_000, home_loan_interest=900_000).allowed()
        assert a["80C"] == 150_000 and a["80D (self/family)"] == 25_000
        assert a["80D (parents)"] == 50_000 and a["80CCD(1B) NPS"] == 50_000
        assert a["24(b) home-loan interest"] == 200_000

    def test_compare_and_breakeven(self):
        from core.tax import compare_regimes, compute_tax, Deductions
        c = compare_regimes(1_800_000)
        assert c["better"] == "new"
        be = c["breakeven_deductions"]
        assert be is not None
        assert compute_tax(1_800_000, "old", Deductions(other=be)).total_tax < c["new"].total_tax
        assert compute_tax(1_800_000, "old", Deductions(other=be - 1_000)).total_tax >= c["new"].total_tax


# ---------------------------------------------------------------------------
# Goals / EMI
# ---------------------------------------------------------------------------

class TestGoals:
    def test_emi_known_value(self):
        from core.goals import emi
        # ₹10 L at 10% for 20 years — standard EMI ≈ ₹9,650
        assert emi(1_000_000, 10, 240) == pytest.approx(9650.22, abs=0.5)

    def test_sip_roundtrip(self):
        from core.goals import sip_required, sip_future_value
        need = sip_required(500_000, 12, 36)
        assert sip_future_value(need, 12, 36) == pytest.approx(500_000, rel=1e-4)

    def test_zero_return(self):
        from core.goals import sip_required, emi
        assert sip_required(12_000, 0, 12) == 1000
        assert emi(12_000, 0, 12) == 1000

    def test_prepayment_saves_interest_and_time(self):
        from core.goals import prepayment_impact
        r = prepayment_impact(1_000_000, 10, 240, extra_monthly=2000)
        assert r["months_saved"] > 0 and r["interest_saved"] > 0

    def test_months_to_goal(self):
        from core.goals import months_to_goal
        assert months_to_goal(10_000, 1000, 0) == 10
        assert months_to_goal(10_000, 0, 0) is None

    def test_plan_goals_priority_and_shortfall(self):
        from core.goals import Goal, plan_goals
        plan = plan_goals([Goal("Laptop", 60_000, 12, priority=2), Goal("Emergency fund", 120_000, 12, priority=1)],
                          monthly_surplus=10_000, annual_return_pct=0)
        assert plan["rows"][0]["goal"] == "Emergency fund"
        assert plan["rows"][0]["on_track"] and not plan["rows"][1]["on_track"]
        assert plan["shortfall"] == pytest.approx(5_000)


# ---------------------------------------------------------------------------
# Assistant
# ---------------------------------------------------------------------------

class TestAssistant:
    def _summary(self):
        txns = [
            _txn("Salary", 40000, "credit", "Salary", "2026-10-01"),
            _txn("Swiggy", 4000, "debit", "Food", "2026-10-03"),
            _txn("Amazon", 6000, "debit", "Shopping", "2026-10-05"),
            _txn("Rent", 12000, "debit", "Rent", "2026-10-02"),
            _txn("NETFLIX", 649, "debit", "Entertainment", "2026-10-04"),
        ]
        return compute_budget(txns), txns

    def test_category_question(self):
        from core.assistant import answer_question
        s, t = self._summary()
        a = answer_question("How much did I spend on food?", s, t)
        assert "₹4,000" in a.text and a.method == "rules"

    def test_affordability(self):
        from core.assistant import answer_question
        s, t = self._summary()
        assert answer_question("Can I afford ₹500 headphones?", s, t).text.startswith("Yes")
        assert answer_question("Can I afford a 1 lakh laptop?", s, t).text.startswith("Not comfortably")

    def test_llm_answer_with_invented_number_is_rejected(self):
        from unittest.mock import MagicMock
        from core.assistant import answer_question
        from llm.schemas import AssistantAnswerLLM
        s, t = self._summary()
        adapter = MagicMock()
        adapter.generate.return_value = AssistantAnswerLLM(answer="You spent ₹7,777 on food.", facts_used=[])
        a = answer_question("How much did I spend on food?", s, t, adapter=adapter)
        assert a.method == "rules" and "7,777" not in a.text

    def test_llm_answer_with_real_numbers_is_kept(self):
        from unittest.mock import MagicMock
        from core.assistant import answer_question
        from llm.schemas import AssistantAnswerLLM
        s, t = self._summary()
        adapter = MagicMock()
        adapter.generate.return_value = AssistantAnswerLLM(answer="Food cost you ₹4,000 this month.", facts_used=["category:Food"])
        a = answer_question("How much did I spend on food?", s, t, adapter=adapter)
        assert a.method == "llm"


# ---------------------------------------------------------------------------
# Link checker & emergency kit
# ---------------------------------------------------------------------------

class TestLinkCheck:
    @pytest.mark.parametrize("url,verdict", [
        ("https://www.onlinesbi.sbi", "safe"),
        ("https://netbanking.hdfcbank.com/netbanking/", "safe"),
        ("http://sbi-kyc-update.xyz/login", "danger"),
        ("bit.ly/3abcd", "danger"),
        ("icicibnak.com", "danger"),
        ("http://192.168.0.5/app.apk", "danger"),
        ("https://xn--hdfcbnk-9za.com", "danger"),
        ("https://paytm.com.secure-login.top", "danger"),
    ])
    def test_verdicts(self, url, verdict):
        from scam.link_check import check_url
        assert check_url(url).verdict == verdict

    def test_extract_skips_emails_and_upi_ids(self):
        from scam.link_check import extract_urls
        urls = extract_urls("Mail care@sbi.co.in or pay rahul@oksbi. Visit www.sbi.co.in now")
        assert urls == ["www.sbi.co.in"]


class TestEmergency:
    def test_plan_starts_with_1930_when_money_lost(self):
        from scam.emergency import action_plan
        plan = action_plan("upi_collect", money_lost=True, hours_since=1)
        assert "1930" in plan[0]["step"] and plan[0]["urgent"]
        assert "golden hour" in plan[0]["why"]

    def test_complaint_draft_contains_details(self):
        from scam.emergency import complaint_draft, IncidentDetails
        text = complaint_draft(IncidentDetails(name="A. Kumar", amount_lost=4999, scam_type="digital_arrest",
                                               transactions=[{"utr": "123456", "amount": 4999, "to_upi_or_account": "x@ybl"}]))
        assert "A. Kumar" in text and "₹4,999" in text and "123456" in text


# ---------------------------------------------------------------------------
# New scam rules
# ---------------------------------------------------------------------------

class TestNewRules:
    @pytest.mark.parametrize("msg,category", [
        ("This is CBI. A parcel in your name contains drugs. Stay on video call, you are under digital arrest.", "digital_arrest"),
        ("Download SBI Rewards.apk to redeem your points now", "malicious_app"),
        ("Scan this QR code to receive your refund of Rs 2,000", "qr_scam"),
        ("Like YouTube videos and earn Rs 150 per task. Join on Telegram", "task_scam"),
        ("Guaranteed returns of 30% every month! Join our VIP stock tips group on WhatsApp", "investment_scam"),
        ("I sent Rs 5000 to you by mistake, please return it on this number", "mistaken_transfer"),
        ("Aapka OTP batao jaldi, account verify karna hai", "otp_request"),
    ])
    def test_rule_categories(self, msg, category):
        from scam.rules import run_rules
        cats = {m.category for m in run_rules(msg).matches}
        assert category in cats

    @pytest.mark.parametrize("msg", [
        "Rs 1,250.00 debited from A/c XX4521 on 14-Nov-26 at SWIGGY. Avl Bal: Rs 12,340.50 —SBI",
        "Your Amazon order has been shipped and will arrive tomorrow.",
        "Download the official SBI YONO app from the Play Store.",
    ])
    def test_safe_messages_stay_low(self, msg):
        from scam.rules import run_rules
        assert run_rules(msg).score < 0.55


class TestStatementImport:
    CSV = (
        "Account Statement,,,,\n"
        "Date,Narration,Withdrawal Amt.,Deposit Amt.,Closing Balance\n"
        "01/11/2026,NEFT-ACME PVT LTD-SALARY,,45000.00,50000.00\n"
        "02/11/2026,UPI/123456789/SWIGGY/okaxis/Payment,450.50,,49549.50\n"
        "not a date,junk,1,,\n"
    )

    def test_statement_converted_and_parsed(self):
        from core.statement import statement_to_sms
        from core.parser import parse_messages
        sms = statement_to_sms(self.CSV)
        assert len(sms) == 2
        parsed = parse_messages(sms)
        assert parsed[0].amount == 45000.0 and parsed[0].transaction_type == "credit"
        assert parsed[1].amount == 450.5 and parsed[1].transaction_type == "debit"
        assert "SWIGGY" in sms[1]

    def test_non_statement_returns_empty(self):
        from core.statement import statement_to_sms
        assert statement_to_sms("raw_sms\nRs 5 debited\n") == []
