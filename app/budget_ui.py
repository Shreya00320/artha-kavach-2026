"""app/budget_ui.py – Smart Budget tab for Artha Kavach.

Provides:
  render_budget_tab(adapter) -> None
"""

import io
import streamlit as st

from app.components import (
    render_budget_metrics,
    render_502030_chart,
    render_category_breakdown,
    render_nudges,
    render_savings_chart,
    render_budget_trust_receipt,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_budget_pipeline(raw_messages: list[str], adapter=None):
    """Parse → categorise → budget → nudges. Returns (summary, nudges, receipt)."""
    from core.parser import parse_messages
    from core.categoriser import categorise_transactions
    from core.budget_engine import compute_budget, compute_pace, detect_recurring
    from core.nudges import generate_nudges
    from core.trust_receipt import build_budget_receipt

    # 1. Parse
    parsed = parse_messages(raw_messages, adapter=adapter)
    n_parsed = sum(1 for p in parsed if p.parse_method != "failed")
    n_failed = sum(1 for p in parsed if p.parse_method == "failed")

    # 2. Categorise
    categorised = categorise_transactions(parsed, adapter=adapter)

    # 3. Budget engine
    summary = compute_budget(categorised)
    summary.n_parsed = n_parsed
    summary.n_failed = n_failed
    summary.recurring = detect_recurring(categorised)
    summary.pace = compute_pace(categorised)

    # 4. Nudges
    nudges = generate_nudges(summary, adapter=adapter)

    # 5. Trust Receipt
    receipt = build_budget_receipt(summary)

    return summary, nudges, receipt


# ---------------------------------------------------------------------------
# Main tab renderer
# ---------------------------------------------------------------------------

def render_budget_tab(adapter=None) -> None:
    st.markdown("## 💰 Smart Budget")
    st.markdown(
        "Paste your bank/UPI SMS messages (one per line), upload a CSV, "
        "or use the **built-in sample dataset** to see your budget breakdown instantly."
    )

    # ---- Input source tabs ----
    src_tab_paste, src_tab_csv, src_tab_sample = st.tabs(
        ["📋 Paste SMS", "📂 Upload CSV", "🎲 Sample data"]
    )

    raw_messages: list[str] | None = None

    with src_tab_paste:
        pasted = st.text_area(
            "Paste SMS messages — one per line",
            height=200,
            placeholder=(
                "Rs 1,250.00 debited from A/c XX4521 on 14-Nov-26 at SWIGGY. "
                "Avl Bal: Rs 12,340.50 —SBI\n"
                "Rs 45,000.00 credited to your A/c XX4521 on 01-Nov-26 "
                "(Salary). Avl Bal: Rs 48,750.00 —SBI\n..."
            ),
            key="budget_paste",
        )
        if st.button("Analyse pasted messages", key="btn_paste"):
            lines = [l.strip() for l in pasted.strip().splitlines() if l.strip()]
            if lines:
                raw_messages = lines
            else:
                st.warning("Please paste at least one message.")

    with src_tab_csv:
        uploaded = st.file_uploader(
            "Upload CSV with a 'message' column (or single-column, no header)",
            type=["csv"],
            key="budget_csv",
        )
        if uploaded and st.button("Analyse CSV", key="btn_csv"):
            import pandas as pd
            df = pd.read_csv(uploaded)
            col = "message" if "message" in df.columns else df.columns[0]
            raw_messages = df[col].dropna().astype(str).tolist()

    with src_tab_sample:
        st.markdown(
            "Loads **120 synthetic bank/UPI SMS messages** across one month "
            "(SBI, HDFC, ICICI, Paytm, PhonePe formats; salary, food, rent, "
            "EMI, shopping, a few unparseable entries)."
        )
        if st.button("▶ Load sample dataset", key="btn_sample", type="primary"):
            import pandas as pd
            try:
                df = pd.read_csv("data/sample_sms.csv")
                col = "message" if "message" in df.columns else df.columns[0]
                raw_messages = df[col].dropna().astype(str).tolist()
                st.success(f"Loaded {len(raw_messages)} sample messages.")
            except FileNotFoundError:
                st.error("Sample data file not found at data/sample_sms.csv.")

    # ---- Run pipeline if we have data ----
    if raw_messages is not None:
        with st.spinner(f"Processing {len(raw_messages)} messages…"):
            try:
                summary, nudges, receipt = _run_budget_pipeline(
                    raw_messages, adapter=adapter
                )
                st.session_state["budget_summary"] = summary
                st.session_state["budget_nudges"]  = nudges
                st.session_state["budget_receipt"] = receipt
            except Exception as exc:
                st.error(f"Pipeline error: {exc}")

    # ---- Render stored results ----
    summary = st.session_state.get("budget_summary")
    if summary is None:
        return

    nudges  = st.session_state.get("budget_nudges", [])
    receipt = st.session_state.get("budget_receipt")

    st.divider()

    # Parse success banner
    n_ok   = summary.n_parsed
    n_fail = summary.n_failed
    total  = n_ok + n_fail
    pct    = round(n_ok / total * 100) if total else 0
    if n_fail > 0:
        st.warning(
            f"Parsed **{n_ok}/{total}** messages ({pct}%). "
            f"{n_fail} could not be parsed and are excluded."
        )
    else:
        st.success(f"Parsed all **{total}** messages successfully.")

    st.markdown(
        f"📅 Period: **{summary.period_start}** → **{summary.period_end}** "
        f"({summary.days_covered} days)"
    )

    # Top-line metrics
    render_budget_metrics(summary)
    st.divider()

    # 50/30/20
    st.markdown("### 50 / 30 / 20 breakdown")
    render_502030_chart(summary)

    # Category breakdown
    st.markdown("### Spending by category")
    render_category_breakdown(summary)

    # Nudges
    st.divider()
    render_nudges(nudges)

    # Recurring payments
    if summary.recurring:
        st.divider()
        st.markdown("### 🔁 Recurring payments detected")
        import pandas as pd
        rec_data = [
            {
                "Merchant":    r.merchant,
                "Category":    r.category,
                "Typical (₹)": f"₹{r.typical_amount:,.0f}",
                "Occurrences": r.occurrences,
                "Months":      ", ".join(r.months),
            }
            for r in summary.recurring
        ]
        st.dataframe(pd.DataFrame(rec_data), hide_index=True, use_container_width=True)

    # Pace projection
    if summary.pace:
        pace = summary.pace
        with st.expander("📈 Month-end pace projection"):
            st.markdown(
                f"At current pace you are on track to spend "
                f"**₹{pace.get('projected_expense', 0):,.0f}** by month end.  \n"
                f"Days elapsed: {pace.get('days_elapsed', '?')} / "
                f"{pace.get('days_in_month', '?')}"
            )

    # Step-up savings chart
    st.divider()
    st.markdown("### 📊 Savings planner")
    st.caption(
        "Illustration based on behavioural-finance research (Save More Tomorrow / SMarT). "
        "Not financial advice."
    )
    col_inc, col_goal, col_mon = st.columns(3)
    with col_inc:
        income_input = st.number_input(
            "Monthly income (₹)", min_value=0, value=int(summary.total_income) or 50000,
            step=1000, key="sav_income"
        )
    with col_goal:
        goal_input = st.number_input(
            "Savings goal (₹)", min_value=0, value=100000, step=5000, key="sav_goal"
        )
    with col_mon:
        months_input = st.slider("Horizon (months)", 6, 36, 12, key="sav_months")

    if income_input > 0 and goal_input > 0:
        from core.savings import compare_plans
        compare = compare_plans(
            income=float(income_input),
            goal=float(goal_input),
            months=months_input,
        )
        render_savings_chart(compare)

    st.divider()
    render_budget_trust_receipt(receipt)
