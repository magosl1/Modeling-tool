"""Tests for DCFEngine — smoke tests covering the happy path and the
WACC > terminal growth invariant."""
from decimal import Decimal

import pytest

from app.services.dcf_engine import DCFEngine


def _build_minimal_inputs():
    """Flat 2-year projection, constant numbers, easy to reason about."""
    years = [2026, 2027]
    pnl = {
        "Revenue": {y: Decimal("1000") for y in years},
        "EBIT": {y: Decimal("200") for y in years},
        "EBT": {y: Decimal("180") for y in years},
        "Tax": {y: Decimal("-45") for y in years},
        "Net Income": {y: Decimal("135") for y in years},
        "D&A": {y: Decimal("50") for y in years},
        "Amortization of Intangibles": {y: Decimal("10") for y in years},
    }
    bs = {
        "Short-Term Debt": {y: Decimal("100") for y in years},
        "Long-Term Debt": {y: Decimal("400") for y in years},
        "Cash & Equivalents": {y: Decimal("200") for y in years},
    }
    cf = {
        "Changes in Working Capital": {y: Decimal("-20") for y in years},
        "Capex": {y: Decimal("-80") for y in years},
    }
    return pnl, bs, cf, years


def test_gordon_growth_requires_wacc_above_g():
    pnl, bs, cf, years = _build_minimal_inputs()
    engine = DCFEngine(
        pnl=pnl, bs=bs, cf=cf, projection_years=years,
        wacc=Decimal("5"), terminal_growth_rate=Decimal("5"),
        exit_multiple=None, discounting_convention="end_of_year",
        shares_outstanding=None, terminal_value_method="gordon_growth",
    )
    with pytest.raises(ValueError):
        engine.run()


def test_run_produces_positive_ev_on_happy_path():
    pnl, bs, cf, years = _build_minimal_inputs()
    engine = DCFEngine(
        pnl=pnl, bs=bs, cf=cf, projection_years=years,
        wacc=Decimal("10"), terminal_growth_rate=Decimal("2"),
        exit_multiple=None, discounting_convention="end_of_year",
        shares_outstanding=Decimal("100"), terminal_value_method="gordon_growth",
    )
    result = engine.run()
    assert result.enterprise_value > 0
    assert result.equity_value == result.enterprise_value - result.net_debt
    # Net debt = 100 + 400 - 200 = 300 (using last projection year)
    assert result.net_debt == Decimal("300")
    assert result.value_per_share == result.equity_value / Decimal("100")
    # Sensitivity table is 5×5.
    assert len(result.sensitivity_table) == 5
    for row in result.sensitivity_table.values():
        assert len(row) == 5


def test_mid_year_convention_yields_higher_pv_than_end_of_year():
    pnl, bs, cf, years = _build_minimal_inputs()
    common = dict(
        pnl=pnl, bs=bs, cf=cf, projection_years=years,
        wacc=Decimal("10"), terminal_growth_rate=Decimal("2"),
        exit_multiple=None, shares_outstanding=None,
        terminal_value_method="gordon_growth",
    )
    eoy = DCFEngine(discounting_convention="end_of_year", **common).run()
    mid = DCFEngine(discounting_convention="mid_year", **common).run()
    assert mid.enterprise_value > eoy.enterprise_value
