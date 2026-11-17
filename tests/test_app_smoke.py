"""
tests/test_app_smoke.py — Headless end-to-end run of the Streamlit app (offline).

Uses streamlit.testing.v1.AppTest to execute app/main.py, click through the
main flows and assert that no exception is raised anywhere on the page.
Skipped automatically if Streamlit (or pandas/altair, which charts need) is unavailable.
"""

import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

st_testing = pytest.importorskip("streamlit.testing.v1")
pytest.importorskip("pandas")
pytest.importorskip("altair")


@pytest.fixture
def app(monkeypatch):
    monkeypatch.chdir(ROOT)
    for var in ("GEMINI_API_KEY", "LLM_API_KEY"):
        monkeypatch.setenv(var, "")          # force offline mode
    at = st_testing.AppTest.from_file(str(ROOT / "app" / "main.py"), default_timeout=120)
    at.run()
    assert not at.exception, at.exception
    return at


def _no_errors(at):
    assert not at.exception, [e.value for e in at.exception]


def test_app_loads_all_tabs(app):
    labels = [t.label for t in app.tabs]
    for expected in ["🛡️ Scam Shield", "💰 Smart Budget", "🎯 Goals & Planner", "🧾 Tax", "💬 Ask Artha", "📖 About"]:
        assert expected in labels


def test_scam_check_flow(app):
    app.text_area(key="scam_textarea").input(
        "Aapka SBI account block ho jayega. Abhi apna OTP share karo: http://sbi-kyc.update.click/verify"
    ).run()
    next(b for b in app.button if b.label == "🔍 Analyse message").click().run()
    _no_errors(app)
    page = " ".join(m.value for m in app.markdown)
    assert "SCAM" in page
    assert "DANGER" in page          # link report rendered


def test_link_and_bulk_and_emergency(app):
    app.text_area(key="link_input").input("bit.ly/3abc and https://www.onlinesbi.sbi").run()
    app.button(key="btn_link").click().run()
    _no_errors(app)
    app.text_area(key="bulk_input").input(
        "Share OTP to receive Rs 5000 refund\nRs 250.00 debited from A/c XX1 on 14-Nov-26 at SWIGGY. Avl Bal: Rs 1,000.00 —SBI"
    ).run()
    app.button(key="btn_bulk").click().run()
    _no_errors(app)
    assert any(m.label == "🚨 Scam" for m in app.metric)


def test_budget_then_goals_tax_chat(app):
    app.button(key="btn_sample").click().run()
    _no_errors(app)
    labels = {m.label for m in app.metric}
    assert {"↔️ Sent to people (not spending)", "Subscriptions per month", "New regime tax"} <= labels

    # Salary-cycle setting recomputes without errors
    app.number_input(key="budget_cycle_day").set_value(27).run()
    _no_errors(app)

    # Ask Artha via a suggested question
    app.button(key="chat_suggest_0").click().run()
    _no_errors(app)
    assert any("₹" in m.value for m in app.markdown)


def test_clear_data(app):
    app.button(key="btn_sample").click().run()
    next(b for b in app.sidebar.button if "Clear all my data" in b.label).click().run()
    _no_errors(app)
    assert "budget_summary" not in app.session_state


def test_category_override_recomputes():
    from app.budget_ui import _apply_overrides
    from core.budget_engine import compute_budget
    from core.categoriser import CategorisedTransaction

    t = CategorisedTransaction(id="X1", raw_message="", amount=500.0, transaction_type="debit",
                               merchant="Mystery shop", vpa=None, date="2026-10-01", balance=None,
                               bank=None, parse_method="regex", confidence=0.9, category="Other",
                               category_method="default", category_confidence=0.0)
    fixed = _apply_overrides([t], {"X1": "Food"})
    assert fixed[0].category == "Food" and fixed[0].category_method == "user"
    assert compute_budget(fixed).by_category == {"Food": 500.0}
