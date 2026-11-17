"""app/tax_ui.py – Old vs new regime comparison (FY 2026-27) for salaried users."""

import streamlit as st

from app.budget_ui import get_budget_state


def _inr(x: float) -> str:
    return f"₹{x:,.0f}"


def render_tax_tab() -> None:
    from core.tax import TAX_YEAR, Deductions, compare_regimes
    from core.insights import tax_tags

    st.markdown("## 🧾 Tax: old vs new regime")
    st.caption(f"{TAX_YEAR} rates · salaried individuals under 60 · estimate only, not tax advice.")

    summary, txns, _ = get_budget_state()
    detected = tax_tags(txns) if txns else {}
    det_80c = sum(i["amount"] for i in detected.get("80C", []))
    det_80d = sum(i["amount"] for i in detected.get("80D", []))
    det_nps = sum(i["amount"] for i in detected.get("80CCD(1B)", []))
    monthly_income = summary.total_income if summary else 0

    c1, c2 = st.columns(2)
    gross = c1.number_input("Annual gross salary (₹)", min_value=0, step=50000,
                            value=int(monthly_income * 12) or 900000, key="tax_gross",
                            help="CTC minus employer PF/gratuity. Pre-filled as 12 × income found in your SMS.")
    other = c2.number_input("Other income — interest, freelance (₹/year)", min_value=0, step=5000, value=0, key="tax_other")

    with st.expander("Old-regime deductions" + (" — pre-filled from your payments" if (det_80c or det_80d or det_nps) else ""),
                     expanded=True):
        a, b, c = st.columns(3)
        s80c = a.number_input("80C: EPF, PPF, ELSS, LIC, tuition (₹)", min_value=0, step=5000,
                              value=int(det_80c * 12) if det_80c else 0, key="tax_80c",
                              help="Includes your EPF contribution from payslip. Cap ₹1.5 L.")
        s80d = b.number_input("80D: health insurance, self/family (₹)", min_value=0, step=1000,
                              value=int(det_80d) if det_80d else 0, key="tax_80d", help="Cap ₹25,000")
        s80dp = c.number_input("80D: parents' health insurance (₹)", min_value=0, step=1000, value=0, key="tax_80dp")
        senior = c.checkbox("Parents are senior citizens", key="tax_senior")
        nps = a.number_input("80CCD(1B): own NPS (₹)", min_value=0, step=5000,
                             value=int(det_nps * 12) if det_nps else 0, key="tax_nps", help="Cap ₹50,000")
        hra = b.number_input("HRA exemption (₹)", min_value=0, step=5000, value=0, key="tax_hra",
                             help="The exempt part of HRA (least of: actual HRA, rent − 10% of basic, 40/50% of basic).")
        hl = c.number_input("Home-loan interest 24(b) (₹)", min_value=0, step=10000, value=0, key="tax_hl",
                            help="Self-occupied property. Cap ₹2 L.")
        oth = a.number_input("Other: 80E, 80G… (₹)", min_value=0, step=1000, value=0, key="tax_oth")
        if det_80c or det_80d or det_nps:
            st.caption("Pre-filled values annualise payments found in your SMS — check them against receipts.")

    d = Deductions(sec_80c=s80c, sec_80d_self=s80d, sec_80d_parents=s80dp, parents_senior=senior,
                   sec_80ccd1b=nps, home_loan_interest=hl, hra_exemption=hra, other=oth)
    res = compare_regimes(gross, d, other)
    new, old = res["new"], res["old"]

    st.divider()
    a, b = st.columns(2)
    a.metric("New regime tax", _inr(new.total_tax), help=f"Effective rate {new.effective_rate_pct}%")
    b.metric("Old regime tax", _inr(old.total_tax), help=f"Effective rate {old.effective_rate_pct}%")
    if res["better"] == "same":
        st.info("Both regimes give the same tax.")
    else:
        st.success(f"**The {res['better']} regime saves you {_inr(res['saving'])} a year** "
                   f"(≈ {_inr(res['saving'] / 12)} a month).")
    be = res["breakeven_deductions"]
    if be is not None and be > 0:
        st.caption(f"The old regime wins only if your deductions (beyond the ₹50,000 standard deduction) "
                   f"exceed about {_inr(be)}. You entered {_inr(d.total_allowed())} after caps.")

    with st.expander("How was this calculated?"):
        for r in (new, old):
            st.markdown(f"**{r.regime.title()} regime** — taxable income {_inr(r.taxable_income)} "
                        f"(gross {_inr(r.gross_income)} − standard deduction {_inr(r.standard_deduction)}"
                        + (f" − deductions {_inr(r.other_deductions)}" if r.other_deductions else "") + ")")
            st.dataframe([{
                "Slab": f"{_inr(s['from'])} – {_inr(s['to']) if s['to'] else 'above'}",
                "Rate": f"{s['rate_pct']:.0f}%", "Income in slab": _inr(s["taxable_in_slab"]), "Tax": _inr(s["tax"]),
            } for s in r.slab_breakdown], hide_index=True, width="stretch")
            st.caption(f"Slab tax {_inr(r.tax_on_slabs)} − 87A rebate {_inr(r.rebate_87a)} − marginal relief "
                       f"{_inr(r.marginal_relief)} + 4% cess {_inr(r.cess)} = **{_inr(r.total_tax)}**")
            for n in r.notes:
                st.caption(f"ℹ️ {n}")
        st.caption("Not covered: surcharge (> ₹50 L), capital gains, senior-citizen slabs, employer NPS 80CCD(2).")
