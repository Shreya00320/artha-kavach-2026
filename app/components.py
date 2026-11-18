"""app/components.py – Reusable Streamlit UI components for Artha Kavach."""

import html

import streamlit as st
from app.styles import VERDICT_COLOUR, VERDICT_EMOJI, NUDGE_ICON


# ---------------------------------------------------------------------------
# Scam Shield components
# ---------------------------------------------------------------------------

_VERDICT_SUB = {
    "scam": "Do not reply, click, pay or share any OTP/PIN.",
    "suspicious": "Don't act on it yet — verify through your bank's official app or number.",
    "safe": "No scam signs found. Still never share OTP/PIN with anyone.",
}


def render_verdict_badge(verdict: str, confidence: float) -> None:
    """Large coloured verdict badge with confidence."""
    colour = VERDICT_COLOUR.get(verdict, "#888")
    emoji  = VERDICT_EMOJI.get(verdict, "❓")
    label  = verdict.upper()
    conf_pct = round(confidence * 100)
    st.markdown(
        f'<div class="verdict-badge" style="background:{colour}">'
        f'{emoji} {label} &nbsp;·&nbsp; {conf_pct}% confidence'
        f'<span class="verdict-sub">{_VERDICT_SUB.get(verdict, "")}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )


def render_red_flags(message: str, red_flags: list) -> None:
    """Show the original message with quoted red-flag text highlighted."""
    if not red_flags:
        st.info("No specific red flags were extracted from this message.")
        return

    # Build highlighted version of original message.
    # Escape user/LLM text before wrapping it in HTML so pasted markup
    # (e.g. <img onerror=...>) is shown as text, not rendered.
    highlighted = html.escape(message)
    for rf in red_flags:
        q = html.escape(rf.quote_from_message or "")
        if q and q in highlighted:
            highlighted = highlighted.replace(
                q, f'<mark class="rf">{q}</mark>', 1
            )

    st.markdown("**Original message (red flags highlighted):**")
    st.markdown(
        f'<div style="background:#1A1F29;border:1px solid #30363D;'
        f'border-radius:8px;padding:14px 18px;font-size:.95rem;'
        f'line-height:1.7;white-space:pre-wrap;">{highlighted}</div>',
        unsafe_allow_html=True,
    )

    st.markdown("**Red flags detected:**")
    for rf in red_flags:
        with st.expander(f"🚩 {rf.flag}  —  *\"{rf.quote_from_message}\"*"):
            st.markdown(rf.why_it_matters)


def render_what_to_do(actions: list[str]) -> None:
    """Numbered action list."""
    if not actions:
        return
    st.markdown("**What to do:**")
    for i, action in enumerate(actions, 1):
        st.markdown(f"{i}. {action}")


def render_trust_receipt(trust_receipt) -> None:
    """Collapsible Trust Receipt panel."""
    if trust_receipt is None:
        return

    with st.expander("🔍 Trust Receipt — see the evidence behind this verdict"):
        # --- Detector votes ---
        if trust_receipt.detector_votes:
            st.markdown("**Detector votes**")
            cols = st.columns(len(trust_receipt.detector_votes))
            for col, vote in zip(cols, trust_receipt.detector_votes):
                css_cls = f"det-{vote.verdict}"
                pct = round(vote.score * 100)
                col.markdown(
                    f'<div class="det-pill {css_cls}">{vote.detector}<br/>'
                    f'<span style="font-weight:400;font-size:.75rem">'
                    f'{vote.verdict} · {pct}%</span></div>',
                    unsafe_allow_html=True,
                )
            agreed = trust_receipt.detectors_agreed
            if agreed is True:
                st.success("All detectors agree ✓")
            elif agreed is False:
                st.warning("Detectors disagree — treat result with extra caution.")

        st.divider()

        # --- Confidence note ---
        if trust_receipt.confidence_note:
            st.markdown(f"ℹ️ {trust_receipt.confidence_note}")

        # --- Verified claims ---
        if trust_receipt.verified_claims:
            st.markdown("**Verified claims**")
            for vc in trust_receipt.verified_claims:
                icon = "✅" if vc.verified else "❌"
                label = "Verified" if vc.verified else "Not verified"
                st.markdown(f"{icon} **{label}** — {vc.claim_text}")
                if vc.evidence_quote:
                    st.caption(f"> {vc.evidence_quote}")

        # --- Sources ---
        if trust_receipt.sources:
            st.markdown("**Sources used**")
            for src in trust_receipt.sources:
                st.markdown(
                    f"- **[{src.source_id}] {src.title}** · {src.publisher}  \n"
                    f"  [{src.url}]({src.url})"
                )
                if src.snippet:
                    st.caption(src.snippet[:200])

        st.divider()
        st.caption(trust_receipt.disclaimer)


# ---------------------------------------------------------------------------
# Smart Budget components
# ---------------------------------------------------------------------------

def render_budget_metrics(summary) -> None:
    """Four top-line metric boxes."""
    c1, c2, c3, c4 = st.columns(4)
    def _box(col, label, value, colour="#58A6FF"):
        col.markdown(
            f'<div class="metric-box">'
            f'<div class="value" style="color:{colour}">₹{value:,.0f}</div>'
            f'<div class="label">{label}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    _box(c1, "Income",   summary.total_income,  "#21C55D")
    _box(c2, "Expenses", summary.total_expense, "#FF4B4B")
    _box(c3, "Net",      summary.net,
         "#21C55D" if summary.net >= 0 else "#FF4B4B")
    _box(c4, "Savings rate",
         summary.savings_rate,  # treat as percentage label below
         "#58A6FF")
    # Override last box to show %
    c4.markdown(
        f'<div class="metric-box" style="margin-top:-80px">'
        f'<div class="value" style="color:#58A6FF">{summary.savings_rate}%</div>'
        f'<div class="label">Savings rate</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def render_502030_chart(summary) -> None:
    """Horizontal stacked bar: actual vs 50/30/20 targets."""
    import pandas as pd
    import altair as alt

    if summary.total_income <= 0:
        st.info("Add income transactions to see the 50/30/20 breakdown.")
        return

    rows = []
    for bucket, actual, target in [
        ("Needs (50%)",   summary.needs_total,   summary.needs_target),
        ("Wants (30%)",   summary.wants_total,   summary.wants_target),
        ("Savings (20%)", summary.savings_total, summary.savings_target),
    ]:
        rows.append({"Bucket": bucket, "Type": "Actual",  "Amount": actual})
        rows.append({"Bucket": bucket, "Type": "Target",  "Amount": target})

    df = pd.DataFrame(rows)
    chart = (
        alt.Chart(df)
        .mark_bar(cornerRadiusEnd=4)
        .encode(
            x=alt.X("Amount:Q", title="₹ Amount"),
            y=alt.Y("Bucket:N", title=""),
            color=alt.Color(
                "Type:N",
                scale=alt.Scale(
                    domain=["Actual", "Target"],
                    range=["#58A6FF", "#30363D"],
                ),
                legend=alt.Legend(orient="bottom"),
            ),
            row=alt.Row("Bucket:N", title="", header=alt.Header(labelAngle=0)),
            tooltip=["Bucket", "Type", alt.Tooltip("Amount:Q", format=",.0f")],
        )
        .properties(width=460, height=50)
        .resolve_scale(y="independent")
    )
    st.altair_chart(chart, width="stretch")


def render_category_breakdown(summary) -> None:
    """Donut chart + table of spend by category."""
    import pandas as pd
    import altair as alt

    if not summary.by_category:
        st.info("No spending categories to display.")
        return

    df = (
        pd.DataFrame(
            [{"Category": k, "Amount": v}
             for k, v in summary.by_category.items() if v > 0]
        )
        .sort_values("Amount", ascending=False)
    )
    if df.empty:
        return

    chart = (
        alt.Chart(df)
        .mark_arc(innerRadius=55, outerRadius=110)
        .encode(
            theta=alt.Theta("Amount:Q"),
            color=alt.Color("Category:N", legend=alt.Legend(orient="right")),
            tooltip=["Category", alt.Tooltip("Amount:Q", format=",.0f")],
        )
        .properties(width=320, height=240)
    )

    col_chart, col_table = st.columns([1, 1])
    with col_chart:
        st.altair_chart(chart, width="stretch")
    with col_table:
        df["Amount (₹)"] = df["Amount"].map(lambda x: f"₹{x:,.0f}")
        st.dataframe(
            df[["Category", "Amount (₹)"]].reset_index(drop=True),
            hide_index=True,
            width="stretch",
        )


def render_nudges(nudges: list[dict]) -> None:
    """Styled nudge cards."""
    if not nudges:
        return
    st.markdown("**💬 Personalised nudges**")
    for n in nudges:
        ntype = n.get("type", "suggestion")
        icon  = NUDGE_ICON.get(ntype, "💡")
        css   = f"nudge-{ntype}"
        st.markdown(
            f'<div class="{css}">{icon} {n["text"]}</div>',
            unsafe_allow_html=True,
        )


def render_savings_chart(compare: dict) -> None:
    """Line chart comparing flat vs step-up savings plans."""
    import pandas as pd
    import altair as alt

    flat   = compare["flat_plan"]
    stepup = compare["stepup_plan"]
    goal   = compare["goal"]

    rows = []
    for i, (f_cum, s_cum) in enumerate(
        zip(flat.cumulative, stepup.cumulative), 1
    ):
        rows.append({"Month": i, "Plan": "Flat savings",          "Saved (₹)": f_cum})
        rows.append({"Month": i, "Plan": "Step-up savings (SMarT)", "Saved (₹)": s_cum})

    df = pd.DataFrame(rows)
    base = alt.Chart(df).encode(
        x=alt.X("Month:O", title="Month"),
        color=alt.Color(
            "Plan:N",
            scale=alt.Scale(
                domain=["Flat savings", "Step-up savings (SMarT)"],
                range=["#58A6FF", "#21C55D"],
            ),
        ),
    )
    lines = base.mark_line(point=True).encode(
        y=alt.Y("Saved (₹):Q", title="Cumulative savings (₹)"),
        tooltip=["Month", "Plan", alt.Tooltip("Saved (₹):Q", format=",.0f")],
    )
    # Goal line
    goal_line = (
        alt.Chart(pd.DataFrame({"goal": [goal]}))
        .mark_rule(strokeDash=[6, 4], color="#FFA500")
        .encode(y="goal:Q")
    )
    st.altair_chart(
        (lines + goal_line).properties(height=300),
        width="stretch",
    )

    adv = compare.get("stepup_advantage_inr", 0)
    gm_flat   = compare.get("goal_met_flat_month")
    gm_stepup = compare.get("goal_met_stepup_month")
    parts = []
    if gm_flat:
        parts.append(f"Flat plan reaches goal by **month {gm_flat}**.")
    if gm_stepup:
        parts.append(f"Step-up plan reaches goal by **month {gm_stepup}**.")
    if adv > 0:
        parts.append(
            f"Step-up saves ₹{adv:,.0f} more over {flat.months} months."
        )
    if parts:
        st.info("  ".join(parts))

    st.caption(flat.disclaimer)


def render_budget_trust_receipt(trust_receipt) -> None:
    """Trust Receipt for the budget module showing code-computed values."""
    if trust_receipt is None:
        return
    with st.expander("🔍 Trust Receipt — how every number was computed"):
        if trust_receipt.code_computed:
            st.markdown("**Code-computed values** (no LLM involved in arithmetic)")
            for cv in trust_receipt.code_computed:
                st.markdown(
                    f"- **{cv.label}**: ₹{cv.value:,.2f} {cv.unit}  \n"
                    f"  Formula: `{cv.formula}`  \n"
                    f"  Inputs: {cv.inputs}"
                )
        if trust_receipt.sources:
            st.markdown("**Reference sources**")
            for src in trust_receipt.sources:
                st.markdown(
                    f"- [{src.title}]({src.url}) · *{src.publisher}*  \n"
                    f"  {src.snippet}"
                )
        st.divider()
        st.caption(trust_receipt.confidence_note)
        st.caption(trust_receipt.disclaimer)
