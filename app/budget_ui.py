"""app/budget_ui.py – Smart Budget tab for Artha Kavach.

Flow: SMS/CSV → parse → categorise (stored in session) → optional salary-cycle
filter and user category corrections → budget engine → insights.

Everything numeric is computed in core/ (plain Python). Results are kept in
st.session_state so the Goals, Tax and Ask Artha tabs can reuse them.

Provides:
  render_budget_tab(adapter) -> None
  get_budget_state() -> (summary, txns, subscriptions) | (None, [], [])
"""

from dataclasses import replace

import streamlit as st

from app.components import (
    render_budget_metrics,
    render_502030_chart,
    render_category_breakdown,
    render_nudges,
    render_budget_trust_receipt,
)

CATEGORY_OPTIONS = [
    "Food", "Transport", "Shopping", "Entertainment", "Utilities", "Healthcare",
    "Education", "Rent", "EMI_Loan", "Savings_Investment", "Salary", "Transfer",
    "Refund", "ATM", "Other",
]

# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def _parse_and_categorise(raw_messages: list[str], adapter=None):
    from core.parser import parse_messages
    from core.categoriser import categorise_transactions
    parsed = parse_messages(raw_messages, adapter=adapter)
    return categorise_transactions(parsed, adapter=adapter)


def _apply_overrides(txns, overrides: dict):
    if not overrides:
        return txns
    return [replace(t, category=overrides[t.id], category_method="user") if t.id in overrides else t for t in txns]


def _compute(txns, cycle_day: int, adapter=None):
    """Budget engine + insights on (optionally cycle-filtered) transactions."""
    from core.budget_engine import compute_budget, compute_pace, detect_recurring
    from core.insights import detect_subscriptions, filter_salary_cycle
    from core.nudges import generate_nudges
    from core.trust_receipt import build_budget_receipt

    failed = [t for t in txns if t.parse_method == "failed"]
    ok = [t for t in txns if t.parse_method != "failed"]
    period = None
    if cycle_day != 1:
        ok, start, end = filter_salary_cycle(ok, cycle_day)
        period = (start, end)

    summary = compute_budget(ok + failed)
    summary.recurring = detect_recurring(ok)
    summary.pace = compute_pace(ok)
    subs = detect_subscriptions(ok)
    nudges = generate_nudges(summary, adapter=adapter)
    receipt = build_budget_receipt(summary)
    return summary, ok, subs, nudges, receipt, period


def get_budget_state():
    """(summary, txns, subscriptions) for other tabs, or (None, [], [])."""
    return (
        st.session_state.get("budget_summary"),
        st.session_state.get("budget_txns_view", []),
        st.session_state.get("budget_subs", []),
    )


def _inr(x: float) -> str:
    return f"₹{x:,.0f}"


# ---------------------------------------------------------------------------
# Main tab renderer
# ---------------------------------------------------------------------------

def render_budget_tab(adapter=None) -> None:
    st.markdown("## 💰 Smart Budget")
    st.markdown(
        "Paste your bank/UPI SMS messages (one per line), upload a CSV, "
        "or use the **built-in sample dataset**. Transfers to people are kept out of "
        "spending, refunds are netted off, and you can correct any category."
    )

    src_tab_paste, src_tab_csv, src_tab_sample = st.tabs(["📋 Paste SMS", "📂 Upload CSV", "🎲 Sample data"])
    raw_messages: list[str] | None = None

    with src_tab_paste:
        pasted = st.text_area(
            "Paste SMS messages — one per line",
            height=200,
            placeholder=(
                "Rs 1,250.00 debited from A/c XX4521 on 14-Nov-26 at SWIGGY. Avl Bal: Rs 12,340.50 —SBI\n"
                "Rs 45,000.00 credited to your A/c XX4521 on 01-Nov-26 (Salary). Avl Bal: Rs 48,750.00 —SBI\n..."
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
            "Bank statement CSV (Date, Narration, Withdrawal, Deposit…) or an SMS CSV with a 'raw_sms'/'message' column",
            type=["csv"], key="budget_csv",
        )
        if uploaded and st.button("Analyse CSV", key="btn_csv"):
            import csv, io
            text = uploaded.getvalue().decode("utf-8-sig", errors="replace")
            from core.statement import statement_to_sms
            stmt = statement_to_sms(text)
            rows = [] if stmt else list(csv.reader(io.StringIO(text)))
            if stmt:
                raw_messages = stmt
                st.success(f"Detected a bank statement — imported {len(stmt)} transactions.")
            elif rows:
                header = [h.strip().lower() for h in rows[0]]
                col = next((header.index(c) for c in ("raw_sms", "message", "sms", "text") if c in header), None)
                body = rows[1:] if col is not None else rows
                col = col or 0
                raw_messages = [r[col].strip() for r in body if len(r) > col and r[col].strip()]

    with src_tab_sample:
        st.markdown(
            "Loads **96 synthetic bank/UPI SMS messages** (SBI, HDFC, ICICI, Axis, Kotak, "
            "PhonePe, GPay, Paytm formats; salary, food, rent, EMI, subscriptions, transfers, "
            "and a few non-transaction messages)."
        )
        if st.button("▶ Load sample dataset", key="btn_sample", type="primary"):
            import csv
            try:
                with open("data/sample_sms.csv", encoding="utf-8") as f:
                    raw_messages = [r["raw_sms"] for r in csv.DictReader(f) if r.get("raw_sms")]
                st.success(f"Loaded {len(raw_messages)} sample messages.")
            except FileNotFoundError:
                st.error("Sample data file not found at data/sample_sms.csv.")

    if raw_messages is not None:
        with st.spinner(f"Processing {len(raw_messages)} messages…"):
            try:
                st.session_state["budget_txns_all"] = _parse_and_categorise(raw_messages, adapter)
                st.session_state["budget_overrides"] = {}
            except Exception as exc:
                st.error(f"Pipeline error: {exc}")

    all_txns = st.session_state.get("budget_txns_all")
    if not all_txns:
        return

    # ---- Settings ----
    st.divider()
    s1, s2 = st.columns([1, 2])
    with s1:
        cycle_day = st.number_input(
            "📅 My month starts on day", min_value=1, max_value=31, value=1, step=1, key="budget_cycle_day",
            help="Salary on the 27th? Set 27 to budget from payday to payday.",
        )
    with s2:
        st.caption(
            "Budget periods follow your salary date instead of the calendar month. "
            "With day 1, the whole dataset is analysed."
        )

    txns = _apply_overrides(all_txns, st.session_state.get("budget_overrides", {}))
    summary, view, subs, nudges, receipt, period = _compute(txns, int(cycle_day), adapter)
    st.session_state.update(budget_summary=summary, budget_txns_view=view, budget_subs=subs)

    # ---- Parse banner ----
    n_ok, n_fail = summary.n_parsed, summary.n_failed
    total = n_ok + n_fail
    if n_fail > 0:
        st.warning(
            f"Parsed **{n_ok}/{total}** messages ({round(n_ok / total * 100) if total else 0}%). "
            f"{n_fail} were not transactions or could not be read — see *Unread messages* below."
        )
    else:
        st.success(f"Parsed all **{total}** messages.")
    if period:
        st.markdown(f"📅 Pay cycle: **{period[0]}** → **{period[1]}**")
    else:
        st.markdown(f"📅 Period: **{summary.period_start}** → **{summary.period_end}** ({summary.days_covered} days)")

    render_budget_metrics(summary)
    m1, m2, m3 = st.columns(3)
    m1.metric("↔️ Sent to people (not spending)", _inr(summary.transfers_out))
    m2.metric("↩️ Refunds netted off", _inr(summary.refunds_total))
    m3.metric("📥 Received from people", _inr(summary.transfers_in))

    # ---- Insights ----
    t_over, t_alerts, t_subs, t_txns, t_tax = st.tabs(
        ["📊 Overview", "🔔 Alerts", "🔁 Subscriptions", "🧾 Transactions", "🧮 Tax hints"]
    )

    with t_over:
        st.markdown("### 50 / 30 / 20 breakdown")
        render_502030_chart(summary)
        st.markdown("### Spending by category")
        render_category_breakdown(summary)
        from core.behaviour import behavioural_nudges
        render_nudges(nudges + behavioural_nudges(summary))

        from core.insights import small_spend_summary, weekly_spend
        small = small_spend_summary(view)
        if small["count"]:
            st.info(
                f"☕ **Small spends:** {small['count']} payments under ₹{small['threshold']:.0f} added up to "
                f"**{_inr(small['total'])}** ({small['share_pct']}% of spending) — about "
                f"{_inr(small['monthly_estimate'])} a month at this rate."
            )
        weeks = weekly_spend(view)
        if len(weeks) >= 2:
            st.markdown("### Weekly spending")
            st.bar_chart({w["week_start"]: w["spend"] for w in weeks}, height=220)

        pace = summary.pace or {}
        if pace.get("current_month_spend"):
            with st.expander("📈 Month-end pace projection"):
                st.markdown(
                    f"In **{pace['current_month']}** you spent **{_inr(pace['current_month_spend'])}** in "
                    f"{pace['days_elapsed']} days — on pace for about **{_inr(pace['projected_month_spend'])}** "
                    f"by the end of the month ({pace['days_in_month']} days)."
                )

    with t_alerts:
        from core.insights import detect_anomalies
        anomalies = detect_anomalies(view)
        st.caption("Only unusual payments are flagged — no alert fatigue.")
        if not anomalies:
            st.success("Nothing unusual in this period. 🎉")
        for a in anomalies:
            box = st.error if a.severity == "high" else st.warning
            box(f"**{_inr(a.amount)}** to **{a.merchant}** ({a.category}, {a.date}) — {a.reason}")
        if summary.recurring:
            st.markdown("#### 🔁 Repeating payments")
            st.dataframe([
                {"Merchant": r.merchant, "Category": r.category, "Typical": _inr(r.typical_amount),
                 "Times": r.occurrences, "Months": ", ".join(r.months)}
                for r in summary.recurring
            ], hide_index=True, width="stretch")

    with t_subs:
        if not subs:
            st.info("No subscriptions found in this data.")
        else:
            total_m = sum(s.monthly_amount for s in subs)
            total_y = sum(s.annual_cost for s in subs)
            c1, c2 = st.columns(2)
            c1.metric("Subscriptions per month", _inr(total_m))
            c2.metric("Per year", _inr(total_y))
            st.dataframe([
                {"Subscription": s.merchant, "Monthly": _inr(s.monthly_amount), "Yearly": _inr(s.annual_cost),
                 "Last charged": s.last_charged, "Detected as": s.source.replace("-", " ")}
                for s in subs
            ], hide_index=True, width="stretch")
            st.caption("Not using one? Cancel it in the app store or the service's own app — "
                       "and revoke UPI AutoPay mandates from your UPI app's 'AutoPay' section.")

    with t_txns:
        st.caption("Wrong category? Change it here — every number on this page recomputes.")
        rows = [{
            "id": t.id, "Date": t.date or "", "Type": t.transaction_type or "", "Amount": t.amount or 0.0,
            "Merchant": t.merchant or "", "Category": t.category,
            "How": {"lookup": "known merchant", "user": "you", "p2p": "person (UPI)", "rule": "rule",
                    "llm": "AI", "default": "guess"}.get(t.category_method.replace("_cached", ""), t.category_method),
        } for t in sorted(view, key=lambda t: t.date or "")]
        import hashlib
        # Edit state belongs to this exact set of rows; a different pay cycle or dataset resets it
        rows_key = hashlib.md5("|".join(r["id"] for r in rows).encode()).hexdigest()[:10]
        edited = st.data_editor(
            rows, key=f"budget_editor_{rows_key}", hide_index=True, width="stretch",
            column_config={
                "id": None,
                "Amount": st.column_config.NumberColumn(format="₹%.2f"),
                "Category": st.column_config.SelectboxColumn(options=CATEGORY_OPTIONS, required=True),
            },
            disabled=["Date", "Type", "Amount", "Merchant", "How"],
        )
        changes = {r["id"]: r["Category"] for r, o in zip(edited, rows) if r["Category"] != o["Category"]}
        if changes:
            st.session_state.setdefault("budget_overrides", {}).update(changes)
            st.rerun()

        from core.insights import transactions_to_rows, rows_to_csv
        st.download_button(
            "⬇️ Export transactions (CSV)",
            rows_to_csv(transactions_to_rows(view)),
            file_name="artha_kavach_transactions.csv",
            mime="text/csv",
        )
        failed = [t for t in txns if t.parse_method == "failed"]
        if failed:
            with st.expander(f"Unread messages ({len(failed)})"):
                for t in failed:
                    st.caption(f"• {t.raw_message[:200]}")

    with t_tax:
        from core.insights import tax_tags
        tags = tax_tags(view)
        if not any(tags.values()):
            st.info("No payments that look like 80C / 80D / NPS deductions in this data.")
        for sec, items in tags.items():
            if items:
                st.markdown(f"**Section {sec}** — {_inr(sum(i['amount'] for i in items))}")
                for i in items:
                    st.caption(f"• {i['date']} · {i['merchant']} · {_inr(i['amount'])}")
        st.caption("These are hints from payment names only — keep receipts and confirm eligibility. "
                   "Compare regimes in the 🧾 Tax tab.")

    st.divider()
    render_budget_trust_receipt(receipt)
