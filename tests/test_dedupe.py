"""Overlapping pastes must not double-count money."""

from core.budget_engine import compute_budget
from core.categoriser import categorise
from core.parser import dedupe_messages, parse_message

SAL = "Rs 45,000.00 credited to a/c XX1234 on 01-11-26 by NEFT-ACME LTD-SALARY. Avl bal Rs 61,200.45"
UPI = "Dear UPI user A/C X1234 debited by 500.0 on date 13Nov26 trf to SWIGGY Refno 633212345678 -SBI"
CHAI = "Rs 20 spent on card XX4321 at CHAI POINT on 12-Nov-26"


def test_identical_messages_with_reference_or_balance_are_removed():
    uniq, n = dedupe_messages([SAL, UPI, SAL, "  " + UPI + "  "])
    assert uniq == [SAL, UPI] and n == 2


def test_identical_short_alerts_without_reference_are_kept():
    uniq, n = dedupe_messages([CHAI, CHAI])
    assert len(uniq) == 2 and n == 0       # could be two real Rs 20 chai payments


def test_pasting_twice_gives_the_same_totals():
    once, _ = dedupe_messages([SAL, UPI])
    twice, _ = dedupe_messages([SAL, UPI, SAL, UPI])
    a = compute_budget([categorise(parse_message(m)) for m in once])
    b = compute_budget([categorise(parse_message(m)) for m in twice])
    assert (a.total_income, a.total_expense) == (b.total_income, b.total_expense)
