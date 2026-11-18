"""app/starter_ui.py – 'First salary' guide and Home (affordability, rent vs buy) calculators.

Education only. No product recommendations, no return promises.
"""

import streamlit as st


def _inr(x: float) -> str:
    return f"₹{x:,.0f}"


def render_first_salary_guide(income: float = 0.0, needs: float = 0.0) -> None:
    st.markdown("### 🌱 First salary — where to start, in order")
    st.caption("Do these in order. Each step protects the next one. Education, not personal advice.")

    inc = st.number_input("Your monthly take-home (₹)", min_value=0, value=int(income) or 30000,
                          step=1000, key="fs_income")
    ess = st.number_input("Monthly essentials: rent, food, bills, EMI (₹)", min_value=0,
                          value=int(needs) or int(inc * 0.5), step=1000, key="fs_needs")
    start_sip = round(inc * 0.10) if inc > 0 else 0

    steps = [
        ("1️⃣ Build a safety cushion first",
         f"Keep 3–6 months of essentials in a savings account or liquid fund so an emergency never "
         f"forces you into debt. For you, 6 months ≈ **{_inr(ess * 6)}**. Start with one month, then grow it."),
        ("2️⃣ Get health insurance",
         "One hospital bill can wipe out years of savings. Check your employer's group cover, but also "
         "consider a personal policy because employer cover usually ends when you change jobs."),
        ("3️⃣ Clear expensive debt",
         "Credit-card balances and 'buy now pay later' dues cost far more than most investments earn. "
         "Pay these off before investing."),
        ("4️⃣ Understand your salary slip",
         "Know your EPF contribution, employer benefits and which tax regime suits you "
         "(see the **Tax** tab). Employer contributions are free money."),
        ("5️⃣ Start a small, automatic SIP",
         f"Begin with about **{_inr(start_sip)}** a month (10% of take-home) in a low-cost, diversified "
         f"index fund, set to debit the day after salary. Raise it with every pay rise (see **Step-up saving**). "
         f"Returns are never guaranteed and can fall. Only invest money you won't need for 5+ years."),
        ("6️⃣ Add goals, then term insurance if anyone depends on you",
         "Give each goal a name, amount and date (see **My goals**). Term insurance matters mainly "
         "once someone relies on your income."),
    ]
    for title, body in steps:
        with st.expander(title, expanded=title.startswith("1")):
            st.markdown(body)

    if ess > 0:
        st.success(f"Your first target: **{_inr(ess)}** (1 month) → **{_inr(ess * 6)}** (6 months) of essentials.")

    st.markdown("#### 🚩 Avoid at the start")
    st.markdown(
        "- **'Guaranteed returns'** or 'double your money' offers: genuine investments cannot guarantee returns.\n"
        "- **Tips from social media or Telegram groups.** Check that an adviser is SEBI-registered "
        "before paying anyone.\n"
        "- **Futures & options trading** as a beginner. SEBI's own studies found most retail traders lose money.\n"
        "- **Anything you can't explain** in one sentence.\n"
        "- **Unregulated platforms.** Use SEBI-registered brokers and fund houses only."
    )
    st.caption("⚖️ Educational tool. Not financial advice. Check current rules and product details before acting.")


def render_home_tab(income: float = 0.0) -> None:
    from core.realestate import affordability, rent_vs_buy

    st.markdown("### 🏠 Home: how much can I afford, and rent or buy?")
    st.caption("Every rate and cost below is **your assumption**. Change them and see. Illustration, not a prediction.")

    t_aff, t_rvb = st.tabs(["💰 Affordability", "⚖️ Rent vs buy"])

    with t_aff:
        c1, c2, c3 = st.columns(3)
        inc = c1.number_input("Monthly take-home (₹)", min_value=0, value=int(income) or 60000, step=5000, key="re_inc")
        ex = c2.number_input("Existing EMIs (₹/month)", min_value=0, value=0, step=1000, key="re_ex")
        cap = c3.slider("Max share of income for EMIs (%)", 20, 50, 40, key="re_cap",
                        help="40% is a common lender rule of thumb. Lower is safer.")
        c4, c5, c6 = st.columns(3)
        rate = c4.number_input("Loan interest (% p.a.)", 1.0, 20.0, 8.5, 0.1, key="re_rate")
        yrs = c5.slider("Loan tenure (years)", 5, 30, 20, key="re_yrs")
        dp = c6.slider("Down payment (%)", 5, 50, 20, key="re_dp")
        if inc > 0:
            a = affordability(float(inc), float(ex), rate, yrs, dp, cap)
            m1, m2, m3 = st.columns(3)
            m1.metric("Comfortable EMI", _inr(a["max_emi"]))
            m2.metric("Max home price", _inr(a["max_price"]))
            m3.metric("Down payment needed", _inr(a["down_payment_needed"]))
            st.caption("Add extra for stamp duty, registration, brokerage and furnishing. These vary by state, so check them. "
                       "Keep your emergency fund separate from the down payment.")

    with t_rvb:
        c1, c2, c3 = st.columns(3)
        price = c1.number_input("Home price (₹)", min_value=100000, value=6000000, step=100000, key="rvb_price")
        rent = c2.number_input("Rent for a similar home (₹/month)", min_value=0, value=18000, step=1000, key="rvb_rent")
        years = c3.slider("Horizon (years)", 3, 30, 15, key="rvb_years")
        c4, c5, c6 = st.columns(3)
        dp = c4.slider("Down payment (%)", 5, 50, 20, key="rvb_dp")
        lrate = c5.number_input("Loan rate (% p.a.)", 1.0, 20.0, 8.5, 0.1, key="rvb_lrate")
        buycost = c6.number_input("One-off buying costs (% of price)", 0.0, 15.0, 6.0, 0.5, key="rvb_buycost",
                                  help="Stamp duty, registration, brokerage. Varies by state.")
        with st.expander("Advanced assumptions"):
            a1, a2, a3, a4 = st.columns(4)
            pg = a1.number_input("Price growth (%/yr)", 0.0, 15.0, 5.0, 0.5, key="rvb_pg")
            rg = a2.number_input("Rent growth (%/yr)", 0.0, 15.0, 5.0, 0.5, key="rvb_rg")
            ir = a3.number_input("Investment return if you rent (%/yr)", 0.0, 15.0, 8.0, 0.5, key="rvb_ir")
            mt = a4.number_input("Yearly upkeep (% of price)", 0.0, 4.0, 1.0, 0.25, key="rvb_mt")
        r = rent_vs_buy(float(price), dp, lrate, years, float(rent), rg, pg, ir, mt, buycost)

        m1, m2, m3 = st.columns(3)
        m1.metric("EMI", _inr(r["emi"]))
        m2.metric("Cash needed up front", _inr(r["upfront_cash"]))
        m3.metric("Yearly upkeep", _inr(r["monthly_maintenance"] * 12))

        verdict = "Buying" if r["winner"] == "buy" else "Renting and investing the difference"
        be = (f" Buying overtakes renting around **year {r['buy_breakeven_year']}**." if r["buy_breakeven_year"]
              else " Buying does not overtake renting within this horizon.")
        st.info(f"With these assumptions, **{verdict}** leaves you about **{_inr(r['difference'])}** "
                f"better off after {years} years." + be)

        import pandas as pd
        df = pd.DataFrame(r["yearly"]).set_index("year").rename(
            columns={"buy": "Buy (home value − loan)", "rent": "Rent + invest"})
        st.line_chart(df)
        st.caption("Change the assumptions: the answer often flips. It depends on price growth vs investment return, "
                   "which nobody can predict. Buying also has non-money value (stability, no landlord). "
                   "This ignores tax benefits and selling costs. ⚖️ Educational, not advice.")
