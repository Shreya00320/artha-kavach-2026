"""Chat calculator: figures come from core.goals; missing inputs fall back to the knowledge answer."""

import pytest

from core.advisor import respond
from core.calculator import answer_calculation, fmt_inr
from core.goals import emi, sip_future_value, sip_required


def test_indian_grouping():
    assert fmt_inr(1161695) == "₹11,61,695" and fmt_inr(999) == "₹999" and fmt_inr(10000000) == "₹1,00,00,000"


@pytest.mark.parametrize("q,expected", [
    ("if I invest 5000 a month at 12% for 10 years how much will I have", fmt_inr(sip_future_value(5000, 12, 120))),
    ("SIP of Rs 10,000 per month for 15 years at 10% return", fmt_inr(sip_future_value(10000, 10, 180))),
    ("emi on a 10 lakh home loan at 8.5% for 20 years", fmt_inr(emi(1_000_000, 8.5, 240))),
    ("EMI for 5 lakh car loan 10% 5 years", fmt_inr(emi(500_000, 10, 60))),
    ("how much sip do I need to reach 1 crore in 20 years at 12%", fmt_inr(sip_required(10_000_000, 12, 240))),
])
def test_numbers_match_the_verified_planner(q, expected):
    ans = answer_calculation(q)
    assert ans and expected in ans


def test_assumptions_and_no_promise_language():
    ans = answer_calculation("invest 5000 a month at 12% for 10 years")
    assert "assumed" in ans and "not guaranteed" in ans


@pytest.mark.parametrize("q", [
    "what is a sip", "should I stop my sip of 5000", "what is the emi", "invest 5000 at 12%",
    "invest 5000 a month at 12% for 100 years", "invest 5000 a month at 900% for 10 years", "", "hello",
])
def test_missing_or_absurd_inputs_return_none(q):
    assert answer_calculation(q) is None


def test_chat_routes_calculations_and_keeps_other_questions():
    r = respond("emi on a 10 lakh home loan at 8.5% for 20 years")
    assert r.intent == "calculator" and "₹8,678" in r.text
    assert respond("what is a sip").intent == "knowledge"
    assert respond("which stock will double my money").intent != "calculator"
