"""Tests for build_debt_schedule.

Covers: empty config short-circuit, bullet-loan maturity, and revolver
auto-draw when cash falls below min_cash.
"""
from decimal import Decimal

from app.services.debt_schedule import build_debt_schedule


def test_empty_config_returns_empty_schedule():
    out = build_debt_schedule(
        proj_years=[2025, 2026],
        revolver_config=None,
        tranches=[],
        pre_interest_ebit={2025: Decimal("100"), 2026: Decimal("100")},
        wc_change={2025: Decimal("0"), 2026: Decimal("0")},
        capex={2025: Decimal("0"), 2026: Decimal("0")},
        tax_rate=Decimal("25"),
        dividends={2025: Decimal("0"), 2026: Decimal("0")},
        opening_cash=Decimal("100"),
    )
    assert out == {}


def test_bullet_loan_amortizes_only_at_maturity():
    tranches = [{
        "id": "t1",
        "principal": Decimal("100"),
        "rate": Decimal("5"),
        "maturity_year": 2026,
        "amortization_method": "bullet",
    }]
    out = build_debt_schedule(
        proj_years=[2025, 2026],
        revolver_config={"limit": 0, "rate": 0, "min_cash": 0},
        tranches=tranches,
        pre_interest_ebit={2025: Decimal("50"), 2026: Decimal("50")},
        wc_change={2025: Decimal("0"), 2026: Decimal("0")},
        capex={2025: Decimal("0"), 2026: Decimal("0")},
        tax_rate=Decimal("25"),
        dividends={2025: Decimal("0"), 2026: Decimal("0")},
        opening_cash=Decimal("500"),
    )
    assert out[2025]["term_loan_amortization"] == Decimal("0")
    assert out[2026]["term_loan_amortization"] == Decimal("100")
    # Interest is negative; in 2025 it's 100 * 5% = 5.
    assert out[2025]["interest_expense"] == Decimal("-5")


def test_revolver_draws_when_cash_below_min():
    # Large capex forces a cash shortfall; revolver should auto-draw.
    out = build_debt_schedule(
        proj_years=[2025],
        revolver_config={"limit": Decimal("200"), "rate": Decimal("6"), "min_cash": Decimal("50")},
        tranches=[],
        pre_interest_ebit={2025: Decimal("10")},
        wc_change={2025: Decimal("0")},
        capex={2025: Decimal("150")},
        tax_rate=Decimal("25"),
        dividends={2025: Decimal("0")},
        opening_cash=Decimal("20"),
    )
    assert out[2025]["revolver_draw"] > Decimal("0")
    assert out[2025]["revolver_balance"] == out[2025]["revolver_draw"]
    assert out[2025]["revolver_repay"] == Decimal("0")
    assert out[2025]["cash_end"] >= Decimal("50") - Decimal("0.01")
