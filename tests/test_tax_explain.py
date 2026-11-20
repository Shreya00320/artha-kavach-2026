"""Tax explainer, HRA and capital-gains calculators, and their chat routes: every figure must equal core.tax."""

import pytest

from core.advisor import respond
from core.calculator import answer_calculation, fmt_inr
from core.tax import Deductions, compare_regimes, compute_tax
from core.tax_explain import capital_gains_tax, explain_tax, hra_exemption, saving_plan


@pytest.mark.parametrize("gross", [500_000, 900_000, 1_275_000, 1_500_000, 1_800_000, 2_500_000, 6_000_000])
def test_explained_totals_equal_the_calculator(gross):
    exp = explain_tax(gross)
    new, old = compute_tax(gross, "new"), compute_tax(gross, "old")
    text = exp.markdown()
    assert fmt_inr(new.total_tax) in text and fmt_inr(old.total_tax) in text
    assert compare_regimes(gross)["better"] in exp.headline


def test_zero_tax_case_is_stated_plainly():
    md = explain_tax(1_200_000).markdown()
    assert "You pay no income tax" in md and "about ₹0 a month" not in md


def test_saving_plan_is_exact_not_estimated():
    d = Deductions(sec_80c=50_000)
    base = compute_tax(2_000_000, "old", d).total_tax
    plan = {p["label"].split(" ")[0]: p for p in saving_plan(2_000_000, d)}
    full = compute_tax(2_000_000, "old", Deductions(sec_80c=150_000)).total_tax
    assert plan["80C"]["saves"] == base - full and plan["80C"]["room"] == 100_000


def test_no_misleading_savings_plan_when_new_regime_wins_whatever_you_do():
    # at 15 lakh even maxed 80C+NPS+80D keeps the new regime cheaper, so no "save more" list
    assert explain_tax(1_500_000).plan == []


def test_plan_shown_when_old_regime_can_win():
    # 150k + 50k + 200k + 600k = 10 lakh of deductions > the ~8 lakh break-even at 25 lakh, with 80D room left
    d = Deductions(sec_80c=150_000, sec_80ccd1b=50_000, home_loan_interest=200_000, hra_exemption=600_000)
    assert compare_regimes(2_500_000, d)["better"] == "old"
    e = explain_tax(2_500_000, d)
    assert [p for p in e.plan if p["label"].startswith("80D")]


def test_hra_least_of_three_rule():
    r = hra_exemption(basic_da=600_000, hra_received=240_000, rent_paid=300_000, metro_50pct=True)
    assert r["exempt"] == 240_000 and r["taxable_hra"] == 0
    r = hra_exemption(600_000, 300_000, 200_000, False)          # rent - 10% basic = 140,000 is the least
    assert r["exempt"] == 140_000 and r["binding_rule"].startswith("Rent paid")
    r = hra_exemption(600_000, 300_000, 50_000, True)            # rent below 10% of basic -> nothing exempt
    assert r["exempt"] == 0
    assert hra_exemption(0, 0, 0, True)["exempt"] == 0


def test_capital_gains_rates_and_exemption():
    r = capital_gains_tax(50_000, 300_000)
    assert r["short_term_tax"] == 10_000 and r["long_term_taxable"] == 175_000 and r["long_term_tax"] == 21_875
    assert r["total"] == round((10_000 + 21_875) * 1.04)
    assert capital_gains_tax(0, 100_000)["total"] == 0                     # inside the Rs 1.25 lakh exemption
    assert capital_gains_tax(-5, -5)["total"] == 0


@pytest.mark.parametrize("q,needle", [
    ("how much income tax on 15 lakh salary", fmt_inr(compute_tax(1_500_000, "new").total_tax)),
    ("tax on 18 lpa with 1.5 lakh in 80c", fmt_inr(compute_tax(1_800_000, "old", Deductions(sec_80c=150_000)).total_tax)),
    ("income tax on Rs 9,50,000", "no income tax"),
    ("tax on 5 lakh ltcg", fmt_inr(capital_gains_tax(0, 500_000)["total"])),
    ("how much tax on stcg of 80000", fmt_inr(capital_gains_tax(80_000, 0)["total"])),
])
def test_chat_routes(q, needle):
    r = respond(q)
    assert r.intent == "calculator" and needle in r.text, r.text[:200]


@pytest.mark.parametrize("q", ["what is tax", "tax saving ELSS vs PPF", "what is ltcg", "emi on 10 lakh loan", "tax", "how much tax on 50"])
def test_non_calculations_are_left_to_the_knowledge_base(q):
    assert answer_calculation(q) is None or q.startswith("emi")


def test_hostile_inputs_do_not_crash():
    for g in (0, -5, 1e12):
        explain_tax(g)
    explain_tax(1_000_000, Deductions(sec_80c=-1, sec_80d_self=1e12))
