"""
core/tax.py — Old vs new income-tax regime calculator for salaried individuals.

Rates: FY 2026-27 (AY 2027-28). Budget 2026 left the slabs unchanged from
FY 2025-26 (Finance Act 2025):

  New regime (default)                  Old regime (age < 60)
    0 – 4 L        nil                     0 – 2.5 L    nil
    4 – 8 L        5%                      2.5 – 5 L    5%
    8 – 12 L       10%                     5 – 10 L     20%
    12 – 16 L      15%                     > 10 L       30%
    16 – 20 L      20%
    20 – 24 L      25%
    > 24 L         30%
  Standard deduction  ₹75,000             ₹50,000
  Sec 87A rebate      up to ₹60,000 if    up to ₹12,500 if
                      taxable ≤ ₹12 L     taxable ≤ ₹5 L
                      (with marginal relief just above ₹12 L)
  Health & education cess: 4% on tax.

Deliberately NOT modelled (the result says so): surcharge (income > ₹50 L),
capital gains / special-rate income, senior-citizen slabs, HRA computation
(enter the exempt HRA you have worked out), employer NPS 80CCD(2).

All arithmetic is plain Python — no AI. Educational estimate, not tax advice.

Public API:
  slab_tax(taxable, slabs) -> float
  compute_tax(gross_salary, regime, deductions=None, other_income=0) -> TaxResult
  compare_regimes(gross_salary, deductions=None, other_income=0) -> dict
  breakeven_deductions(gross_salary, other_income=0) -> float
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

TAX_YEAR = "FY 2026-27 (AY 2027-28)"
CESS_RATE = 0.04
SURCHARGE_THRESHOLD = 5_000_000

NEW_SLABS = [(400_000, 0.0), (800_000, 0.05), (1_200_000, 0.10), (1_600_000, 0.15),
             (2_000_000, 0.20), (2_400_000, 0.25), (float("inf"), 0.30)]
OLD_SLABS = [(250_000, 0.0), (500_000, 0.05), (1_000_000, 0.20), (float("inf"), 0.30)]

NEW_STD_DEDUCTION = 75_000
OLD_STD_DEDUCTION = 50_000
NEW_REBATE_LIMIT, NEW_REBATE_MAX = 1_200_000, 60_000
OLD_REBATE_LIMIT, OLD_REBATE_MAX = 500_000, 12_500

# Old-regime deduction caps
CAPS = {
    "80C": 150_000,              # EPF, PPF, ELSS, LIC, tuition, home-loan principal…
    "80D_self": 25_000,          # health insurance, self/family (< 60)
    "80D_parents": 50_000,       # 25,000 if parents < 60; 50,000 if senior citizens
    "80CCD1B": 50_000,           # additional own NPS contribution
    "24b_home_loan_interest": 200_000,   # self-occupied property
}


@dataclass
class Deductions:
    """Old-regime deductions (amounts actually paid/eligible, before caps)."""
    sec_80c: float = 0.0
    sec_80d_self: float = 0.0
    sec_80d_parents: float = 0.0
    parents_senior: bool = False
    sec_80ccd1b: float = 0.0
    home_loan_interest: float = 0.0
    hra_exemption: float = 0.0       # computed by the user (least of the three rules)
    other: float = 0.0               # 80E education-loan interest, 80G donations, etc.

    def allowed(self) -> dict[str, float]:
        """Each deduction after applying its statutory cap."""
        parents_cap = 50_000 if self.parents_senior else 25_000
        return {
            "80C": min(max(self.sec_80c, 0), CAPS["80C"]),
            "80D (self/family)": min(max(self.sec_80d_self, 0), CAPS["80D_self"]),
            "80D (parents)": min(max(self.sec_80d_parents, 0), parents_cap),
            "80CCD(1B) NPS": min(max(self.sec_80ccd1b, 0), CAPS["80CCD1B"]),
            "24(b) home-loan interest": min(max(self.home_loan_interest, 0), CAPS["24b_home_loan_interest"]),
            "HRA exemption": max(self.hra_exemption, 0),
            "Other (80E/80G…)": max(self.other, 0),
        }

    def total_allowed(self) -> float:
        return sum(self.allowed().values())


@dataclass
class TaxResult:
    regime: str                      # "new" | "old"
    gross_income: float
    standard_deduction: float
    other_deductions: float
    taxable_income: float
    tax_on_slabs: float
    rebate_87a: float
    marginal_relief: float
    tax_after_rebate: float
    cess: float
    total_tax: float
    effective_rate_pct: float        # total_tax / gross income
    monthly_tax: float
    slab_breakdown: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _breakdown(taxable: float, slabs: list[tuple[float, float]]) -> list[dict]:
    rows, lower = [], 0.0
    for upper, rate in slabs:
        if taxable <= lower:
            break
        portion = min(taxable, upper) - lower
        rows.append({
            "from": lower, "to": upper if upper != float("inf") else None,
            "rate_pct": rate * 100, "taxable_in_slab": round(portion, 2),
            "tax": round(portion * rate, 2),
        })
        lower = upper
    return rows


def slab_tax(taxable: float, slabs: list[tuple[float, float]]) -> float:
    """Tax on `taxable` using progressive slabs (before rebate and cess)."""
    return round(sum(r["tax"] for r in _breakdown(max(taxable, 0.0), slabs)), 2)


def compute_tax(
    gross_salary: float,
    regime: str = "new",
    deductions: Optional[Deductions] = None,
    other_income: float = 0.0,
    salaried: bool = True,
) -> TaxResult:
    """Income tax for one regime.

    Args:
        gross_salary: annual gross salary (₹).
        regime: "new" or "old".
        deductions: old-regime deductions; ignored under the new regime.
        other_income: interest, freelance etc. taxed at slab rates.
        salaried: standard deduction applies only to salary/pension.
    """
    if regime not in ("new", "old"):
        raise ValueError("regime must be 'new' or 'old'")
    gross = max(gross_salary, 0.0) + max(other_income, 0.0)
    notes: list[str] = []

    if regime == "new":
        std = min(NEW_STD_DEDUCTION, max(gross_salary, 0)) if salaried else 0.0
        other_ded = 0.0
        slabs, rebate_limit, rebate_max = NEW_SLABS, NEW_REBATE_LIMIT, NEW_REBATE_MAX
        if deductions and deductions.total_allowed() > 0:
            notes.append("Most deductions (80C, 80D, HRA, home-loan interest) are not allowed in the new regime.")
    else:
        std = min(OLD_STD_DEDUCTION, max(gross_salary, 0)) if salaried else 0.0
        other_ded = deductions.total_allowed() if deductions else 0.0
        slabs, rebate_limit, rebate_max = OLD_SLABS, OLD_REBATE_LIMIT, OLD_REBATE_MAX

    taxable = max(gross - std - other_ded, 0.0)
    taxable = float(int(taxable / 10) * 10)   # income is rounded down to the nearest ₹10
    tax = slab_tax(taxable, slabs)

    rebate = min(tax, rebate_max) if taxable <= rebate_limit else 0.0
    relief = 0.0
    if regime == "new" and taxable > rebate_limit:
        # Marginal relief: tax payable may not exceed income above ₹12 L
        excess = taxable - rebate_limit
        if tax > excess:
            relief = round(tax - excess, 2)
    tax_after = round(max(tax - rebate - relief, 0.0), 2)
    cess = round(tax_after * CESS_RATE, 2)
    total = round(tax_after + cess)

    if gross > SURCHARGE_THRESHOLD:
        notes.append("Income above ₹50 L attracts surcharge, which this calculator does not add.")
    if rebate:
        notes.append(f"Sec 87A rebate of ₹{rebate:,.0f} applied (taxable income ≤ ₹{rebate_limit:,.0f}).")
    if relief:
        notes.append(f"Marginal relief of ₹{relief:,.0f} applied just above the ₹12 L rebate limit.")

    return TaxResult(
        regime=regime,
        gross_income=round(gross, 2),
        standard_deduction=std,
        other_deductions=round(other_ded, 2),
        taxable_income=taxable,
        tax_on_slabs=tax,
        rebate_87a=round(rebate, 2),
        marginal_relief=relief,
        tax_after_rebate=tax_after,
        cess=cess,
        total_tax=float(total),
        effective_rate_pct=round(total / gross * 100, 2) if gross else 0.0,
        monthly_tax=round(total / 12, 2),
        slab_breakdown=_breakdown(taxable, slabs),
        notes=notes,
    )


def compare_regimes(
    gross_salary: float,
    deductions: Optional[Deductions] = None,
    other_income: float = 0.0,
) -> dict:
    """Compute both regimes and say which is cheaper and by how much."""
    new = compute_tax(gross_salary, "new", deductions, other_income)
    old = compute_tax(gross_salary, "old", deductions, other_income)
    if new.total_tax < old.total_tax:
        better, saving = "new", old.total_tax - new.total_tax
    elif old.total_tax < new.total_tax:
        better, saving = "old", new.total_tax - old.total_tax
    else:
        better, saving = "same", 0.0
    return {
        "tax_year": TAX_YEAR,
        "new": new,
        "old": old,
        "better": better,
        "saving": round(saving, 2),
        "breakeven_deductions": breakeven_deductions(gross_salary, other_income),
    }


def breakeven_deductions(gross_salary: float, other_income: float = 0.0) -> Optional[float]:
    """Smallest total old-regime deductions (beyond the standard deduction) at
    which the old regime becomes cheaper than the new one. None if it never does
    within ₹10 L of deductions. Found by bisection on a monotone function."""
    target = compute_tax(gross_salary, "new", None, other_income).total_tax

    def old_tax(d: float) -> float:
        return compute_tax(gross_salary, "old", Deductions(other=d), other_income).total_tax

    if old_tax(0) < target:
        return 0.0
    hi = 1_000_000.0
    if old_tax(hi) >= target:
        return None
    lo = 0.0
    for _ in range(40):
        mid = (lo + hi) / 2
        if old_tax(mid) < target:
            hi = mid
        else:
            lo = mid
    return round(hi / 100) * 100.0   # round to ₹100
