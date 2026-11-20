"""core/realestate.py – home affordability and rent-vs-buy. Plain arithmetic, no LLM.

Every input is user-set (rates, growth, costs); outputs are illustrations, not
predictions. Costs like stamp duty/registration vary by state, so they are an input.

  affordability(...)  -> dict
  rent_vs_buy(...)    -> dict
"""

from __future__ import annotations

from core.goals import emi


def _principal_for_emi(max_emi: float, annual_rate_pct: float, months: int) -> float:
    r = annual_rate_pct / 1200
    if max_emi <= 0 or months <= 0:
        return 0.0
    if r == 0:
        return max_emi * months
    f = (1 + r) ** months
    return max_emi * (f - 1) / (r * f)


def affordability(monthly_income: float, existing_emi: float, annual_rate_pct: float,
                  years: int, down_payment_pct: float, max_emi_pct: float = 40.0) -> dict:
    """Max EMI = max_emi_pct% of take-home minus existing EMIs; price from loan + down payment."""
    max_emi = max(0.0, monthly_income * max_emi_pct / 100 - existing_emi)
    loan = _principal_for_emi(max_emi, annual_rate_pct, years * 12)
    dp = down_payment_pct / 100
    price = loan / (1 - dp) if dp < 1 else 0.0
    return {
        "max_emi": round(max_emi), "max_loan": round(loan),
        "max_price": round(price), "down_payment_needed": round(price * dp),
    }


def rent_vs_buy(price: float, down_payment_pct: float, loan_rate_pct: float, years: int,
                monthly_rent: float, rent_growth_pct: float = 5.0, price_growth_pct: float = 5.0,
                invest_return_pct: float = 8.0, maintenance_pct_of_price: float = 1.0,
                buy_costs_pct: float = 6.0) -> dict:
    """Month-by-month net-worth comparison over `years`.

    Buy:  property value - loan balance (down payment + one-off costs spent up front).
    Rent: the same up-front cash invested, plus every month's (buy outflow - rent) invested.
    """
    years = max(int(years), 1)
    months = years * 12
    down = price * down_payment_pct / 100
    loan = price - down
    e = emi(loan, loan_rate_pct, months) if loan > 0 else 0.0
    upfront = down + price * buy_costs_pct / 100
    maint_m = price * maintenance_pct_of_price / 100 / 12
    rm = loan_rate_pct / 1200
    ir = invest_return_pct / 1200

    balance, portfolio, rent = loan, upfront, monthly_rent
    yearly, breakeven = [], None
    for m in range(1, months + 1):
        balance = balance * (1 + rm) - e if loan > 0 else 0.0
        if m > 1 and (m - 1) % 12 == 0:
            rent *= 1 + rent_growth_pct / 100
        buy_out = e + maint_m
        portfolio = portfolio * (1 + ir) + (buy_out - rent)   # invest the gap (may be negative)
        if m % 12 == 0:
            y = m // 12
            value = price * (1 + price_growth_pct / 100) ** y
            buy_nw, rent_nw = value - max(balance, 0.0), portfolio
            yearly.append({"year": y, "buy": round(buy_nw), "rent": round(rent_nw)})
            if breakeven is None and buy_nw >= rent_nw:
                breakeven = y
    last = yearly[-1] if yearly else {"buy": 0, "rent": 0}
    return {
        "emi": round(e), "upfront_cash": round(upfront), "monthly_maintenance": round(maint_m),
        "yearly": yearly, "buy_final": last["buy"], "rent_final": last["rent"],
        "winner": "buy" if last["buy"] >= last["rent"] else "rent",
        "difference": abs(last["buy"] - last["rent"]), "buy_breakeven_year": breakeven,
    }
