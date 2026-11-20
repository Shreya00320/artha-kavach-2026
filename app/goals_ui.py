"""app/goals_ui.py – Goals & Planner tab: emergency fund, goals, SIP, EMI, step-up savings.

All maths in core/goals.py and core/savings.py (plain Python). Illustrations only —
returns are assumptions the user sets, not predictions.
"""

import streamlit as st

from app.budget_ui import get_budget_state


def _inr(x: float) -> str:
    return f"₹{x:,.0f}"


def render_goals_tab() -> None:
    from core.goals import (
        Goal, emergency_fund, emi, loan_summary, plan_goals, prepayment_impact,
        sip_future_value, sip_required, years_months, months_to_goal, rule_of_72,
    )

    st.markdown("## 🎯 Goals & Tax")
    summary, _, _ = get_budget_state()
    income = float(summary.total_income) if summary and summary.total_income else 0.0
    needs = float(summary.needs_total) if summary and summary.needs_total else 0.0
    surplus = float(summary.net) if summary and summary.net > 0 else 0.0
    if summary is None:
        st.info("Tip: load your SMS in 💰 Smart Budget first — this tab then pre-fills from your real numbers.")

    t_first, t_ef, t_goals, t_tax, t_sip, t_emi, t_step, t_home = st.tabs(
        ["🌱 First salary", "🛟 Emergency fund", "🎯 My goals", "🧾 Tax: old vs new", "📈 SIP calculator",
         "🏦 Loan / EMI", "🪜 Step-up saving", "🏠 Home"]
    )

    with t_first:
        from app.starter_ui import render_first_salary_guide
        render_first_salary_guide(income, needs)

    with t_home:
        from app.starter_ui import render_home_tab
        render_home_tab(income)

    with t_tax:
        from app.tax_ui import render_tax_tab
        render_tax_tab()

    with t_ef:
        c1, c2, c3 = st.columns(3)
        essentials = c1.number_input("Monthly essentials (₹)", min_value=0, step=1000,
                                     value=int(needs) or 20000, key="ef_needs",
                                     help="Rent, food, bills, EMIs — pre-filled from your 'needs' spend.")
        months_cover = c2.slider("Months to cover", 3, 12, 6, key="ef_months")
        current = c3.number_input("Already saved for emergencies (₹)", min_value=0, step=1000, value=0, key="ef_current")
        ef = emergency_fund(essentials, months_cover, current)
        st.progress(ef["progress_pct"] / 100, text=f"{ef['progress_pct']}% of {_inr(ef['target'])}")
        a, b, c = st.columns(3)
        a.metric("Target", _inr(ef["target"]))
        b.metric("Still needed", _inr(ef["gap"]))
        c.metric("Months covered now", ef["months_cover_now"])
        if ef["gap"] > 0:
            monthly = st.number_input("I can set aside per month (₹)", min_value=0, step=500,
                                      value=int(min(surplus, ef["gap"])) or 3000, key="ef_monthly")
            m = months_to_goal(ef["gap"], monthly, 6.5, 0)
            st.info(f"At {_inr(monthly)}/month in a savings account or liquid fund (~6.5% a year, assumed), "
                    f"you'd close the gap in **{years_months(m)}**.")
        st.caption("Keep it somewhere safe and instantly accessible — not in stocks or locked deposits.")

    with t_goals:
        st.caption("Add goals in the table. Priority 1 is funded first from your monthly surplus.")
        default = st.session_state.get("goals_table") or [
            {"Goal": "Emergency fund", "Target (₹)": int(needs * 6) or 120000, "Months": 12, "Saved (₹)": 0, "Priority": 1},
            {"Goal": "New laptop", "Target (₹)": 70000, "Months": 10, "Saved (₹)": 10000, "Priority": 2},
            {"Goal": "Goa trip", "Target (₹)": 30000, "Months": 6, "Saved (₹)": 0, "Priority": 3},
        ]
        edited = st.data_editor(default, num_rows="dynamic", hide_index=True, width="stretch", key="goals_editor",
                                column_config={
                                    "Target (₹)": st.column_config.NumberColumn(min_value=0, step=1000),
                                    "Months": st.column_config.NumberColumn(min_value=1, max_value=600, step=1),
                                    "Saved (₹)": st.column_config.NumberColumn(min_value=0, step=1000),
                                    "Priority": st.column_config.NumberColumn(min_value=1, max_value=9, step=1),
                                })
        c1, c2 = st.columns(2)
        monthly_surplus = c1.number_input("Money I can save each month (₹)", min_value=0, step=500,
                                          value=int(surplus) or 15000, key="goal_surplus")
        ret = c2.slider("Expected return (% a year, assumption)", 0.0, 12.0, 7.0, 0.5, key="goal_ret")
        goals = []
        for r in edited:
            try:
                if r.get("Goal") and float(r.get("Target (₹)") or 0) > 0 and int(r.get("Months") or 0) > 0:
                    goals.append(Goal(str(r["Goal"]), float(r["Target (₹)"]), int(r["Months"]),
                                      float(r.get("Saved (₹)") or 0), int(r.get("Priority") or 9)))
            except (TypeError, ValueError):
                continue
        if goals:
            plan = plan_goals(goals, monthly_surplus, ret)
            st.dataframe([{
                "Goal": p["goal"], "Needs / month": _inr(p["monthly_needed"]),
                "Funded / month": _inr(p["monthly_funded"]),
                "Status": "✅ on track" if p["on_track"] else f"⏳ ~{years_months(p['eta_months_at_funded_rate'])}",
                "Progress": f"{p['progress_pct']}%",
            } for p in plan["rows"]], hide_index=True, width="stretch")
            if plan["shortfall"] > 0:
                st.warning(f"Your goals need **{_inr(plan['total_monthly_needed'])}/month** — "
                           f"{_inr(plan['shortfall'])} more than you can save. Stretch a deadline or trim a target.")
            else:
                st.success(f"All goals fit, with {_inr(plan['left_over'])}/month to spare.")

    with t_sip:
        mode = st.radio("I want to…", ["Find the SIP for a goal", "See what a SIP grows to"], horizontal=True, key="sip_mode")
        c1, c2, c3 = st.columns(3)
        rate = c2.slider("Expected return (% a year)", 0.0, 15.0, 12.0, 0.5, key="sip_rate")
        years = c3.slider("Years", 1, 40, 5, key="sip_years")
        if mode.startswith("Find"):
            goal = c1.number_input("Goal amount (₹)", min_value=1000, step=10000, value=500000, key="sip_goal")
            need = sip_required(goal, rate, years * 12)
            st.metric("Monthly SIP needed", _inr(need))
            st.caption(f"You invest {_inr(need * years * 12)}; assumed growth adds the rest.")
        else:
            monthly = c1.number_input("Monthly SIP (₹)", min_value=100, step=500, value=5000, key="sip_amt")
            fv = sip_future_value(monthly, rate, years * 12)
            a, b = st.columns(2)
            a.metric("Value after period", _inr(fv))
            b.metric("Of which you invested", _inr(monthly * years * 12))
        doubling = (f"roughly doubles every {rule_of_72(rate)} years (rule of 72)" if rate > 0
                    else "does not grow at all")
        st.caption(f"At {rate}% a year money {doubling}. "
                   "Equity returns are not guaranteed and can be negative in some years.")

    with t_emi:
        c1, c2, c3 = st.columns(3)
        principal = c1.number_input("Loan amount (₹)", min_value=1000, step=10000, value=500000, key="emi_p")
        rate = c2.number_input("Interest rate (% a year)", min_value=0.0, max_value=50.0, value=10.5, step=0.25, key="emi_r")
        months = c3.number_input("Tenure (months)", min_value=1, max_value=480, value=60, step=6, key="emi_n")
        ls = loan_summary(principal, rate, int(months))
        a, b, c = st.columns(3)
        a.metric("EMI", _inr(ls["emi"]))
        b.metric("Total interest", _inr(ls["total_interest"]))
        c.metric("Interest share", f"{ls['interest_share_pct']}%")
        if income:
            ratio = ls["emi"] / income * 100
            (st.warning if ratio > 30 else st.info)(
                f"This EMI is {ratio:.0f}% of your monthly income. Lenders and planners usually suggest keeping "
                f"all EMIs under about 30–40%.")
        extra = st.number_input("Extra I could pay every month (₹)", min_value=0, step=500, value=2000, key="emi_extra")
        if extra:
            pi = prepayment_impact(principal, rate, int(months), extra)
            st.success(f"Paying {_inr(extra)} extra each month clears the loan **{pi['months_saved']} months sooner** "
                       f"and saves **{_inr(pi['interest_saved'])}** in interest.")
        st.caption("Check prepayment charges with your lender (floating-rate home loans to individuals usually have none).")

    with t_step:
        st.caption("Save a little now and raise it with each pay rise — based on 'Save More Tomorrow' "
                   "(Thaler & Benartzi, 2004). Illustration, not advice.")
        c1, c2, c3 = st.columns(3)
        inc = c1.number_input("Monthly income (₹)", min_value=0, value=int(income) or 50000, step=1000, key="sav_income")
        goal = c2.number_input("Savings goal (₹)", min_value=0, value=100000, step=5000, key="sav_goal")
        horizon = c3.slider("Horizon (months)", 6, 36, 12, key="sav_months")
        if inc > 0 and goal > 0:
            from core.savings import compare_plans
            from app.components import render_savings_chart
            render_savings_chart(compare_plans(income=float(inc), goal=float(goal), months=horizon))
