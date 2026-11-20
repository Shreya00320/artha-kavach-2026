"""core/tax_explain.py — explain the tax calculation in plain words, find real savings, and small tax calculators.

Everything numeric comes from core.tax (plain Python, unit-tested). This module only arranges those numbers into
sentences, so there is nothing for an AI to get wrong.

  explain_tax(gross, deductions=None, other_income=0) -> TaxExplanation
  saving_plan(gross, deductions=None, other_income=0) -> list[dict]   # what filling each deduction would save
  hra_exemption(basic_da, hra_received, rent_paid, metro_50pct) -> dict
  capital_gains_tax(short_term, long_term) -> dict

Educational estimate only — not tax advice. Surcharge, senior-citizen slabs and employer NPS are not modelled.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Optional

from core.tax import CAPS, TAX_YEAR, Deductions, compare_regimes, compute_tax
from core.calculator import fmt_inr

CGT_SHORT_RATE = 0.20          # listed equity / equity funds, held 12 months or less
CGT_LONG_RATE = 0.125          # held more than 12 months
CGT_LONG_EXEMPT = 125_000      # per financial year
CESS = 0.04


@dataclass
class TaxExplanation:
    headline: str
    steps_new: list[str] = field(default_factory=list)
    steps_old: list[str] = field(default_factory=list)
    why: list[str] = field(default_factory=list)
    plan: list[dict] = field(default_factory=list)
    caveats: list[str] = field(default_factory=list)

    def markdown(self, short: bool = False) -> str:
        out = [f"**{self.headline}**", ""]
        out.append("**New regime**")
        out += [f"- {s}" for s in self.steps_new]
        if not short:
            out += ["", "**Old regime**"] + [f"- {s}" for s in self.steps_old]
        out += ["", "**Why**"] + [f"- {s}" for s in self.why]
        if self.plan and not short:
            out += ["", "**What could save more tax**"] + [f"- {p['text']}" for p in self.plan]
        out += ["", f"_{' '.join(self.caveats)}_"]
        return "\n".join(out)


def _steps(r) -> list[str]:
    steps = [f"Start with {fmt_inr(r.gross_income)}; take off the standard deduction of {fmt_inr(r.standard_deduction)}"
             + (f" and deductions of {fmt_inr(r.other_deductions)}" if r.other_deductions else "")
             + f" → taxable income {fmt_inr(r.taxable_income)}."]
    for s in r.slab_breakdown:
        if s["tax"] > 0:
            top = fmt_inr(s["to"]) if s["to"] else "above"
            steps.append(f"{s['rate_pct']:.0f}% on {fmt_inr(s['taxable_in_slab'])} (slab {fmt_inr(s['from'])}–{top}) = {fmt_inr(s['tax'])}")
    if r.rebate_87a:
        steps.append(f"Section 87A rebate of {fmt_inr(r.rebate_87a)} (taxable income is within the rebate limit).")
    if r.marginal_relief:
        steps.append(f"Marginal relief of {fmt_inr(r.marginal_relief)} so you never pay more than the income above ₹12 lakh.")
    if r.total_tax == 0:
        steps.append("**You pay no income tax.**")
    else:
        steps.append(f"Add 4% health & education cess {fmt_inr(r.cess)} → **{fmt_inr(r.total_tax)}** a year (about {fmt_inr(r.monthly_tax)} a month).")
    return steps


def saving_plan(gross: float, deductions: Optional[Deductions] = None, other_income: float = 0.0) -> list[dict]:
    """For each old-regime deduction with headroom: how much extra tax that would save (computed, not estimated)."""
    d = deductions or Deductions()
    base = compute_tax(gross, "old", d, other_income).total_tax
    items = [
        ("80C (EPF, PPF, ELSS, life insurance…)", "sec_80c", CAPS["80C"]),
        ("80CCD(1B) own NPS contribution", "sec_80ccd1b", CAPS["80CCD1B"]),
        ("80D health insurance for self/family", "sec_80d_self", CAPS["80D_self"]),
        ("24(b) home-loan interest", "home_loan_interest", CAPS["24b_home_loan_interest"]),
    ]
    plan = []
    for label, attr, cap in items:
        used = min(max(getattr(d, attr), 0.0), cap)
        room = cap - used
        if room <= 0:
            continue
        saved = base - compute_tax(gross, "old", replace(d, **{attr: cap}), other_income).total_tax
        if saved > 0:
            plan.append({"label": label, "room": room, "saves": saved,
                         "text": f"{label}: {fmt_inr(room)} of room left — using it would cut your old-regime tax by about {fmt_inr(saved)}."})
    return sorted(plan, key=lambda p: -p["saves"])


def explain_tax(gross: float, deductions: Optional[Deductions] = None, other_income: float = 0.0) -> TaxExplanation:
    res = compare_regimes(gross, deductions, other_income)
    new, old = res["new"], res["old"]
    d = deductions or Deductions()
    if res["better"] == "same":
        head = f"On {fmt_inr(gross)} the two regimes give the same tax ({fmt_inr(new.total_tax)})."
    else:
        head = (f"On {fmt_inr(gross)} the {res['better']} regime is cheaper: {fmt_inr(min(new.total_tax, old.total_tax))} "
                f"instead of {fmt_inr(max(new.total_tax, old.total_tax))} — you save {fmt_inr(res['saving'])} a year.")
    why: list[str] = []
    if new.total_tax == 0:
        why.append("Your taxable income under the new regime is within the ₹12 lakh rebate limit, so you pay no income tax at all.")
    elif res["better"] == "new":
        why.append("The new regime's lower slab rates outweigh the deductions you have entered for the old regime.")
    elif res["better"] == "old":
        why.append(f"Your deductions ({fmt_inr(d.total_allowed())} after caps) are large enough to beat the new regime's lower slab rates.")
    be = res["breakeven_deductions"]
    if be:
        why.append(f"The old regime would only win if your deductions beyond the standard deduction exceeded about {fmt_inr(be)}"
                   f" (you have {fmt_inr(d.total_allowed())} after caps).")
    elif be is None and res["better"] != "old" and new.total_tax > 0:
        why.append("Even very large deductions would not make the old regime cheaper at this income.")
    plan = saving_plan(gross, deductions, other_income)
    show_plan = res["better"] == "old"
    if plan and res["better"] == "new":
        maxed = replace(d, sec_80c=CAPS["80C"], sec_80ccd1b=CAPS["80CCD1B"], sec_80d_self=CAPS["80D_self"],
                        home_loan_interest=max(d.home_loan_interest, 0))
        old_max = compute_tax(gross, "old", maxed, other_income).total_tax
        if old_max < new.total_tax:
            show_plan = True
            why.append(f"If you used the full 80C, NPS and 80D limits the old regime would cost {fmt_inr(old_max)} — "
                       f"{fmt_inr(new.total_tax - old_max)} less than the new regime.")
        else:
            why.append("Even if you filled the 80C, NPS and 80D limits, the new regime would still be cheaper, so there is "
                       "no need to buy products just to save tax.")
    caveats = [f"{TAX_YEAR} rates, salaried under 60. Surcharge, capital gains, senior-citizen slabs and employer NPS are not "
               "included. Educational estimate, not tax advice."]
    return TaxExplanation(head, _steps(new), _steps(old), why, plan if show_plan else [], caveats)


def hra_exemption(basic_da: float, hra_received: float, rent_paid: float, metro_50pct: bool) -> dict:
    """Annual HRA exemption (old regime only): the least of actual HRA, rent minus 10% of basic+DA, and 50%/40% of basic+DA."""
    basic_da, hra_received, rent_paid = max(basic_da, 0.0), max(hra_received, 0.0), max(rent_paid, 0.0)
    rules = [
        ("Actual HRA received", hra_received),
        ("Rent paid minus 10% of basic + DA", max(rent_paid - 0.10 * basic_da, 0.0)),
        (f"{'50' if metro_50pct else '40'}% of basic + DA", basic_da * (0.50 if metro_50pct else 0.40)),
    ]
    label, exempt = min(rules, key=lambda r: r[1])
    notes = ["HRA exemption is available only in the old regime.",
             "Keep rent receipts; if annual rent is above ₹1 lakh you need the landlord's PAN."]
    if rent_paid * 1.0 > 0 and rent_paid <= 0.10 * basic_da:
        notes.append("Your rent is not more than 10% of basic + DA, so no HRA is exempt.")
    return {"exempt": round(exempt), "taxable_hra": round(max(hra_received - exempt, 0.0)),
            "rules": [(n, round(v)) for n, v in rules], "binding_rule": label, "notes": notes}


def capital_gains_tax(short_term: float, long_term: float) -> dict:
    """Tax on listed equity / equity-fund gains: 20% short-term; long-term above ₹1.25 lakh at 12.5%; plus 4% cess."""
    st, lt = max(short_term, 0.0), max(long_term, 0.0)
    lt_taxable = max(lt - CGT_LONG_EXEMPT, 0.0)
    st_tax, lt_tax = st * CGT_SHORT_RATE, lt_taxable * CGT_LONG_RATE
    cess = (st_tax + lt_tax) * CESS
    return {
        "short_term_tax": round(st_tax), "long_term_exempt_used": round(min(lt, CGT_LONG_EXEMPT)),
        "long_term_taxable": round(lt_taxable), "long_term_tax": round(lt_tax), "cess": round(cess),
        "total": round(st_tax + lt_tax + cess),
        "notes": ["Listed equity shares and equity mutual funds only (12 months or less = short-term).",
                  "Enter net gains after setting off losses. The 87A rebate does not reduce this tax.",
                  "Debt funds, gold, property and surcharge are not covered."],
    }
