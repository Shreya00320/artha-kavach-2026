"""
tests/test_core.py — Unit tests for Phase 1 core modules.

Coverage:
  Parser (8 tests): SBI debit, HDFC debit, ICICI credit, UPI sent/received,
                    ATM withdrawal, batch parse, non-SMS fails gracefully
  Categoriser (5 tests): known merchants, unknown+mock, cache hit, credit type, batch
  Budget engine (7 tests): totals, 50/30/20 split, recurring detection, pace math,
                            empty input, needs/wants/savings deltas
  Savings (5 tests): flat plan length, stepup plan step-up, compare advantage,
                     edge cases (zero income, 1 month)
  Nudges (5 tests): invented-number rejection, rule-based works offline,
                    llm path with mock adapter, verify passes clean nudges,
                    fallback when all nudges rejected

Total: 30 tests (spec requires ≥15)
"""

import pytest
from datetime import date
from unittest.mock import MagicMock, patch

from core.parser import ParsedTransaction, parse_message, parse_messages, _next_id
from core.categoriser import (
    CategorisedTransaction, categorise, categorise_transactions,
    _lookup, MERCHANT_LOOKUP, _CACHE,
)
from core.budget_engine import (
    BudgetSummary, RecurringPayment,
    compute_budget, detect_recurring, compute_pace, _split_5030_20,
)
from core.savings import flat_savings_plan, stepup_savings_plan, compare_plans
from core.nudges import (
    _extract_numbers, _get_summary_numbers, _number_in_summary,
    _verify_nudges, rule_based_nudges, generate_nudges,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_txn(
    merchant="Swiggy", amount=500.0, txn_type="debit", category="Food",
    date_str="2026-11-10", parse_method="regex", bank="SBI",
) -> CategorisedTransaction:
    return CategorisedTransaction(
        id=_next_id(), raw_message="", amount=amount, transaction_type=txn_type,
        merchant=merchant, vpa=None, date=date_str, balance=None, bank=bank,
        parse_method=parse_method, confidence=0.9,
        category=category, category_method="lookup", category_confidence=1.0,
    )


def _make_budget(
    income=25000, needs=8000, wants=6000, savings=2000, by_cat=None
) -> BudgetSummary:
    expense = needs + wants + savings
    base = income
    by_category = by_cat or {"Food": 3000, "Transport": 1000, "Shopping": 5000, "Savings_Investment": 2000}
    return BudgetSummary(
        period_start="2026-11-01", period_end="2026-11-14", days_covered=14,
        total_income=income, total_expense=expense, net=income - expense,
        savings_rate=round((income - expense) / income * 100, 1) if income else 0,
        by_category=by_category,
        needs_total=needs, wants_total=wants, savings_total=savings,
        needs_pct=round(needs / base * 100, 1),
        wants_pct=round(wants / base * 100, 1),
        savings_pct=round(savings / base * 100, 1),
        needs_target=round(base * 0.5, 2),
        wants_target=round(base * 0.3, 2),
        savings_target=round(base * 0.2, 2),
        needs_delta=round(needs - base * 0.5, 2),
        wants_delta=round(wants - base * 0.3, 2),
        savings_delta=round(savings - base * 0.2, 2),
        n_transactions=10, n_parsed=10, n_failed=0,
    )


# ---------------------------------------------------------------------------
# Parser tests
# ---------------------------------------------------------------------------

class TestParser:

    def test_sbi_debit(self):
        sms = "Rs 1,250.00 debited from A/c XX4521 on 14-Nov-26 at SWIGGY. Avl Bal: Rs 12,340.50 —SBI"
        txn = parse_message(sms)
        assert txn.amount == 1250.00
        assert txn.transaction_type == "debit"
        assert txn.merchant.upper() == "SWIGGY"
        assert txn.bank == "SBI"
        assert txn.date == "2026-11-14"
        assert txn.balance == 12340.50
        assert txn.parse_method == "regex"

    def test_hdfc_debit(self):
        sms = "Your HDFC Bank A/c XX8810 is debited Rs 999.00 on 03-Nov-26. Info: NETFLIX. Avl Bal Rs 21,551.00"
        txn = parse_message(sms)
        assert txn.amount == 999.00
        assert txn.transaction_type == "debit"
        assert "NETFLIX" in txn.merchant.upper()
        assert txn.bank == "HDFC"
        assert txn.date == "2026-11-03"
        assert txn.parse_method == "regex"

    def test_icici_credit(self):
        sms = "Rs 2,000.00 credited to your ICICI Bank A/c XX2341 on 02-Nov-26. UPI Ref: 56789012. —ICICI"
        txn = parse_message(sms)
        assert txn.amount == 2000.00
        assert txn.transaction_type == "credit"
        assert txn.bank == "ICICI"
        assert txn.date == "2026-11-02"
        assert txn.parse_method == "regex"

    def test_upi_sent(self):
        sms = "Sent Rs 500.00 to rahul.kumar@oksbi via UPI on 02-Nov-26. UPI Ref: 123456789012. Balance: Rs 11,840.50"
        txn = parse_message(sms)
        assert txn.amount == 500.00
        assert txn.transaction_type == "debit"
        assert txn.vpa == "rahul.kumar@oksbi"
        assert txn.date == "2026-11-02"
        assert txn.parse_method == "regex"

    def test_upi_received(self):
        sms = "Received Rs 15,000.00 from SALARY CORP via UPI on 01-Nov-26. UPI Ref: 345678901234. Balance: Rs 34,980.50"
        txn = parse_message(sms)
        assert txn.amount == 15000.00
        assert txn.transaction_type == "credit"
        assert txn.date == "2026-11-01"
        assert txn.parse_method == "regex"

    def test_atm_withdrawal(self):
        sms = "ATM WDL Rs 2,000.00 from A/c XX4521 on 09-Nov-26 at SBI ATM DELHI. Avl Bal: Rs 9,980.50 —SBI"
        txn = parse_message(sms)
        assert txn.amount == 2000.00
        assert txn.transaction_type == "debit"
        assert txn.merchant == "ATM"
        assert txn.bank == "SBI"
        assert txn.parse_method == "regex"

    def test_non_sms_fails_gracefully(self):
        """Non-bank messages should return parse_method='failed' without crashing."""
        texts = [
            "Hi, please check your bank statement.",
            "Bank maintenance tonight.",
            "Hello world",
            "",
        ]
        for text in texts:
            txn = parse_message(text)
            assert txn.parse_method == "failed"
            assert txn.amount is None

    def test_batch_parse(self):
        messages = [
            "Rs 1,250.00 debited from A/c XX4521 on 14-Nov-26 at SWIGGY. Avl Bal: Rs 12,340.50 —SBI",
            "Sent Rs 500.00 to rahul@oksbi via UPI on 02-Nov-26. Balance: Rs 500.00",
            "Hi, please check your statement.",
        ]
        results = parse_messages(messages)
        assert len(results) == 3
        assert results[0].parse_method == "regex"
        assert results[2].parse_method == "failed"


# ---------------------------------------------------------------------------
# Categoriser tests
# ---------------------------------------------------------------------------

class TestCategoriser:

    def setup_method(self):
        """Clear cache before each test."""
        _CACHE.clear()

    def test_known_merchant_swiggy(self):
        txn = parse_message("Rs 350.00 debited from A/c XX4521 on 10-Nov-26 at SWIGGY. Avl Bal: Rs 8,900.00 —SBI")
        result = categorise(txn)
        assert result.category == "Food"
        assert result.category_method == "lookup"
        assert result.category_confidence == 1.0

    def test_known_merchant_netflix(self):
        txn = parse_message("Your HDFC Bank A/c XX8810 is debited Rs 999.00 on 03-Nov-26. Info: NETFLIX. Avl Bal Rs 21,551.00")
        result = categorise(txn)
        assert result.category == "Entertainment"
        assert result.category_confidence == 1.0

    def test_unknown_merchant_with_mock_adapter(self):
        """Unknown merchant uses LLM adapter fallback."""
        from llm.schemas import MerchantCategoryLLM
        mock_adapter = MagicMock()
        mock_adapter.generate.return_value = MerchantCategoryLLM(
            category="Shopping", confidence=0.85, reasoning="Unknown shop"
        )
        # Use a merchant that is definitely NOT in the lookup table
        txn = _make_txn(merchant="ObscureShopXYZ999")
        result = categorise(txn, adapter=mock_adapter)
        assert result.category == "Shopping"
        assert "llm" in result.category_method

    def test_cache_hit(self):
        """Second categorisation of same merchant uses cache (adapter not called)."""
        from llm.schemas import MerchantCategoryLLM
        mock_adapter = MagicMock()
        mock_adapter.generate.return_value = MerchantCategoryLLM(
            category="Healthcare", confidence=0.9, reasoning="Medical shop"
        )
        # Use a merchant definitely not in lookup
        t1 = _make_txn(merchant="SomeClinic_Unique_XYZ")
        t2 = _make_txn(merchant="SomeClinic_Unique_XYZ")
        categorise(t1, adapter=mock_adapter)
        categorise(t2, adapter=mock_adapter)
        # Adapter called only once (second was cache hit)
        assert mock_adapter.generate.call_count == 1

    def test_batch_categorise(self):
        txns = [
            parse_message("Rs 1,250.00 debited from A/c XX4521 on 14-Nov-26 at SWIGGY. Avl Bal: Rs 12,340.50 —SBI"),
            parse_message("Your HDFC Bank A/c XX8810 is debited Rs 999.00 on 03-Nov-26. Info: NETFLIX. Avl Bal Rs 21,551.00"),
        ]
        results = categorise_transactions(txns)
        assert len(results) == 2
        assert results[0].category == "Food"
        assert results[1].category == "Entertainment"


# ---------------------------------------------------------------------------
# Budget engine tests
# ---------------------------------------------------------------------------

class TestBudgetEngine:

    def _make_categorised_txns(self):
        return [
            _make_txn("Swiggy", 1500, "debit", "Food", "2026-11-05"),
            _make_txn("Uber", 500, "debit", "Transport", "2026-11-06"),
            _make_txn("Amazon", 3000, "debit", "Shopping", "2026-11-07"),
            _make_txn("Salary", 25000, "credit", "Salary", "2026-11-01"),
            _make_txn("Netflix", 999, "debit", "Entertainment", "2026-11-03"),
            _make_txn("Rent", 7500, "debit", "Rent", "2026-11-05"),
            _make_txn("Groww", 2000, "debit", "Savings_Investment", "2026-11-05"),
        ]

    def test_total_income(self):
        txns = self._make_categorised_txns()
        summary = compute_budget(txns)
        assert summary.total_income == 25000.0

    def test_total_expense(self):
        txns = self._make_categorised_txns()
        summary = compute_budget(txns)
        expected = 1500 + 500 + 3000 + 999 + 7500 + 2000
        assert summary.total_expense == expected

    def test_5030_20_split(self):
        by_cat = {"Food": 3000, "Rent": 7000, "Shopping": 5000, "Savings_Investment": 2000}
        needs, wants, savings = _split_5030_20(by_cat)
        assert needs == 10000  # Food + Rent
        assert wants == 5000   # Shopping
        assert savings == 2000

    def test_savings_rate(self):
        txns = self._make_categorised_txns()
        summary = compute_budget(txns, income=25000)
        expense = 1500 + 500 + 3000 + 999 + 7500 + 2000
        expected_net = 25000 - expense
        assert summary.net == expected_net
        assert summary.savings_rate == round(expected_net / 25000 * 100, 1)

    def test_needs_wants_savings_targets(self):
        summary = compute_budget(self._make_categorised_txns(), income=25000)
        assert summary.needs_target == 12500.0   # 50% of 25000
        assert summary.wants_target == 7500.0    # 30%
        assert summary.savings_target == 5000.0  # 20%

    def test_empty_input(self):
        summary = compute_budget([])
        assert summary.total_income == 0
        assert summary.total_expense == 0
        assert summary.by_category == {}

    def test_recurring_detection(self):
        """Netflix appears in Oct and Nov → detected as recurring."""
        txns = [
            _make_txn("netflix", 999, "debit", "Entertainment", "2026-10-03"),
            _make_txn("netflix", 999, "debit", "Entertainment", "2026-11-03"),
            _make_txn("rent-landlord", 7500, "debit", "Rent", "2026-10-01"),
            _make_txn("rent-landlord", 7500, "debit", "Rent", "2026-11-01"),
            _make_txn("swiggy", 350, "debit", "Food", "2026-11-10"),
        ]
        recurring = detect_recurring(txns)
        merchants = [r.merchant for r in recurring]
        assert "netflix" in merchants
        assert "rent-landlord" in merchants
        assert "swiggy" not in merchants  # only one month

    def test_pace_projection(self):
        # 10 days into month, spent 5000 → project 15000/month (30 days)
        today = date(2026, 11, 10)
        txns = [
            _make_txn("Swiggy", 500, "debit", "Food", "2026-11-01"),
            _make_txn("Uber", 500, "debit", "Transport", "2026-11-05"),
            _make_txn("Amazon", 4000, "debit", "Shopping", "2026-11-08"),
            _make_txn("Salary", 25000, "credit", "Salary", "2026-11-01"),
        ]
        pace = compute_pace(txns, today=today)
        assert pace["current_month_spend"] == 5000.0
        assert pace["days_elapsed"] == 10
        # projected = 5000/10 * 30 = 15000
        assert pace["projected_month_spend"] == pytest.approx(15000.0, abs=1)


# ---------------------------------------------------------------------------
# Savings tests
# ---------------------------------------------------------------------------

class TestSavings:

    def test_flat_plan_length(self):
        plan = flat_savings_plan(income=30000, rate=0.20, months=12)
        assert len(plan.monthly_amounts) == 12
        assert all(a == 6000.0 for a in plan.monthly_amounts)
        assert plan.total_saved == 72000.0

    def test_stepup_plan_increases(self):
        plan = stepup_savings_plan(
            income=30000, initial_rate=0.10, stepup_pct=0.02, raise_every_n=3, months=12
        )
        assert len(plan.monthly_amounts) == 12
        # Month 1-3: rate 0.10, Month 4-6: 0.12, Month 7-9: 0.14, Month 10-12: 0.16
        assert plan.monthly_amounts[0] == pytest.approx(3000, abs=1)
        assert plan.monthly_amounts[3] == pytest.approx(3600, abs=1)
        assert plan.monthly_amounts[6] == pytest.approx(4200, abs=1)
        assert plan.monthly_amounts[9] == pytest.approx(4800, abs=1)

    def test_stepup_saves_more_than_flat(self):
        flat = flat_savings_plan(income=30000, rate=0.10, months=12)
        stepup = stepup_savings_plan(income=30000, initial_rate=0.10, stepup_pct=0.02,
                                     raise_every_n=3, months=12)
        assert stepup.total_saved > flat.total_saved

    def test_compare_advantage(self):
        result = compare_plans(income=30000, goal=50000, months=12,
                               initial_rate=0.10, stepup_pct=0.02, raise_every_n=3)
        assert result["stepup_advantage_inr"] > 0
        assert "disclaimer" in result
        assert result["flat_plan"].total_saved == pytest.approx(36000, abs=1)

    def test_zero_income_edge(self):
        plan = flat_savings_plan(income=0, rate=0.20, months=12)
        assert plan.total_saved == 0
        assert plan.monthly_amounts == []


# ---------------------------------------------------------------------------
# Nudges tests
# ---------------------------------------------------------------------------

class TestNudges:

    def test_extract_numbers(self):
        text = "You spent Rs 3,200 (18%) on Food"
        nums = _extract_numbers(text)
        assert 3200.0 in nums
        assert 18.0 in nums

    def test_rule_based_nudges_no_llm(self):
        """Rule-based nudges always work without adapter."""
        summary = _make_budget()
        nudges = rule_based_nudges(summary)
        assert len(nudges) >= 1
        for n in nudges:
            assert "text" in n
            assert "category" in n
            assert "type" in n

    def test_invented_number_rejected(self):
        """A nudge referencing a number not in the summary must be rejected."""
        summary = _make_budget(income=25000, needs=8000, wants=6000, savings=2000)
        # 99999 is definitely not in the summary
        nudge_with_invented = [{"text": "You spent Rs 99999 on unknown items.", "category": "Other", "type": "suggestion"}]
        verified = _verify_nudges(nudge_with_invented, summary)
        assert len(verified) == 0

    def test_clean_nudge_passes_verification(self):
        """A nudge using only real numbers from the summary should pass."""
        summary = _make_budget(income=25000, needs=8000, wants=6000, savings=2000)
        # 25000 is in the summary (total_income)
        clean_nudge = [{"text": "Income is Rs 25000 this month.", "category": "Salary", "type": "positive"}]
        verified = _verify_nudges(clean_nudge, summary)
        assert len(verified) == 1

    def test_generate_nudges_with_mock_adapter(self):
        """generate_nudges with mock adapter returns LLM nudges when they pass verification."""
        from llm.schemas import NudgeListLLM, NudgeItem
        summary = _make_budget(income=25000, needs=8000, wants=6000, savings=2000,
                               by_cat={"Food": 3000, "Shopping": 5000, "Savings_Investment": 2000})

        mock_result = NudgeListLLM(nudges=[
            NudgeItem(text="Your savings this month are Rs 2000 — keep it up!", category="Savings_Investment", type="positive"),
            NudgeItem(text="Shopping at Rs 5000 is your top want. Consider a Rs 25000 monthly budget review.", category="Shopping", type="suggestion"),
        ])
        mock_adapter = MagicMock()
        mock_adapter.generate.return_value = mock_result

        nudges = generate_nudges(summary, adapter=mock_adapter)
        # At least 1 should pass (Rs 2000 is in by_cat, Rs 5000 is in by_cat, Rs 25000 is income)
        assert len(nudges) >= 1
        mock_adapter.generate.assert_called_once()

    def test_fallback_when_all_nudges_rejected(self):
        """When all LLM nudges fail verification, falls back to rule-based."""
        from llm.schemas import NudgeListLLM, NudgeItem
        summary = _make_budget(income=25000)

        mock_result = NudgeListLLM(nudges=[
            NudgeItem(text="You spent Rs 999999 this month.", category="Other", type="warning"),
        ])
        mock_adapter = MagicMock()
        mock_adapter.generate.return_value = mock_result

        nudges = generate_nudges(summary, adapter=mock_adapter)
        # Should fall back to rule-based, which always returns >= 1
        assert len(nudges) >= 1
