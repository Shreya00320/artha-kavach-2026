"""app/styles.py – Shared CSS and colour tokens for Artha Kavach UI."""

# Verdict colours (badge background)
VERDICT_COLOUR = {
    "scam":       "#FF4B4B",
    "suspicious": "#FFA500",
    "safe":       "#21C55D",
}

VERDICT_EMOJI = {
    "scam":       "🚨",
    "suspicious": "⚠️",
    "safe":       "✅",
}

NUDGE_ICON = {
    "positive":   "🌟",
    "suggestion": "💡",
    "warning":    "⚠️",
}

# Inject once per page via st.markdown
GLOBAL_CSS = """
<style>
/* ---- overall app ---- */
[data-testid="stAppViewContainer"] { background: #0F1117; }
[data-testid="stSidebar"]          { background: #161B22; }
h1, h2, h3, h4                     { font-family: 'Segoe UI', sans-serif; }

/* ---- verdict badge ---- */
.verdict-badge {
    display: inline-block;
    padding: 10px 28px;
    border-radius: 999px;
    font-size: 1.5rem;
    font-weight: 800;
    letter-spacing: .03em;
    color: #fff;
    margin-bottom: 12px;
}

/* ---- Trust Receipt card ---- */
.trust-card {
    background: #161B22;
    border: 1px solid #30363D;
    border-radius: 12px;
    padding: 16px 20px;
    margin-top: 8px;
}
.trust-card h4 { margin-top: 0; color: #58A6FF; font-size: .95rem; }

/* ---- red-flag highlight ---- */
mark.rf { background: #FF4B4B33; color: #FF9090; border-radius: 4px;
           padding: 1px 4px; font-weight: 600; }

/* ---- detector pill ---- */
.det-pill {
    display: inline-block;
    padding: 3px 12px;
    border-radius: 999px;
    font-size: .8rem;
    font-weight: 700;
    margin-right: 6px;
    color: #fff;
}
.det-scam       { background: #FF4B4B; }
.det-suspicious { background: #FFA500; }
.det-safe       { background: #21C55D; }

/* ---- nudge card ---- */
.nudge-positive   { border-left: 4px solid #21C55D; padding: 8px 14px; background:#0D2818; border-radius:6px; margin:6px 0; }
.nudge-suggestion { border-left: 4px solid #58A6FF; padding: 8px 14px; background:#0D1B2E; border-radius:6px; margin:6px 0; }
.nudge-warning    { border-left: 4px solid #FFA500; padding: 8px 14px; background:#2B1D00; border-radius:6px; margin:6px 0; }

/* ---- metric label ---- */
.metric-box {
    background:#161B22; border:1px solid #30363D; border-radius:10px;
    padding:14px; text-align:center;
}
.metric-box .value { font-size:1.6rem; font-weight:800; }
.metric-box .label { font-size:.8rem; color:#8B949E; margin-top:2px; }
</style>
"""
