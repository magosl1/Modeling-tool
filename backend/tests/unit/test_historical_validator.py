"""Tests for the 8-rule historical validator.

These cover the happy path and one failure case per rule. The goal is to pin
down the contract: given known-bad inputs, the validator must surface a
ValidationError pointing at the right tab/line/year.
"""
from decimal import Decimal

from app.services.historical_validator import validate_historical_data


def _valid_pnl(year=2024):
    # Revenue + COGS = Gross Profit; GP + OpEx = EBIT; EBIT ± Non-Op = EBT;
    # EBT + Tax = Net Income. Convention: expenses are stored as negative.
    return {
        "Revenue": {year: Decimal("1000")},
        "Cost of Goods Sold": {year: Decimal("-400")},
        "Gross Profit": {year: Decimal("600")},
        "SG&A": {year: Decimal("-100")},
        "R&D": {year: Decimal("-50")},
        "D&A": {year: Decimal("-30")},
        "Amortization of Intangibles": {year: Decimal("-10")},
        "Other OpEx": {year: Decimal("-20")},
        "EBIT": {year: Decimal("390")},
        "Interest Income": {year: Decimal("5")},
        "Interest Expense": {year: Decimal("-25")},
        "Other Non-Operating Income / (Expense)": {year: Decimal("0")},
        "EBT": {year: Decimal("370")},
        "Tax": {year: Decimal("-74")},
        "Net Income": {year: Decimal("296")},
    }


def _valid_bs(year=2024):
    # Assets - (Liabilities + Equity) ≈ 0. Liabilities+Equity stored negative
    # so the validator checks `total_assets + total_le == 0`.
    return {
        "PP&E Gross": {year: Decimal("500")},
        "Accumulated Depreciation": {year: Decimal("-100")},
        "Net PP&E": {year: Decimal("400")},
        "Intangibles Gross": {year: Decimal("100")},
        "Accumulated Amortization": {year: Decimal("-20")},
        "Net Intangibles": {year: Decimal("80")},
        "Goodwill": {year: Decimal("50")},
        "Inventories": {year: Decimal("70")},
        "Accounts Receivable": {year: Decimal("60")},
        "Prepaid Expenses & Other Current Assets": {year: Decimal("10")},
        "Cash & Equivalents": {year: Decimal("200")},
        "Non-Operating Assets": {year: Decimal("30")},
        "Accounts Payable": {year: Decimal("-40")},
        "Accrued Liabilities": {year: Decimal("-20")},
        "Other Current Liabilities": {year: Decimal("-10")},
        "Other Long-Term Liabilities": {year: Decimal("-30")},
        "Short-Term Debt": {year: Decimal("-50")},
        "Long-Term Debt": {year: Decimal("-300")},
        "Share Capital": {year: Decimal("-200")},
        "Retained Earnings": {year: Decimal("-240")},
        "Other Equity (AOCI, Treasury Stock, etc.)": {year: Decimal("-10")},
    }


def _valid_cf():
    return {}


def test_valid_inputs_produce_no_errors():
    errors = validate_historical_data(_valid_pnl(), _valid_bs(), _valid_cf(), [2024])
    assert errors == []


def test_rule3_gross_profit_mismatch():
    pnl = _valid_pnl()
    pnl["Gross Profit"][2024] = Decimal("999")  # Wrong: should be 600
    errors = validate_historical_data(pnl, _valid_bs(), _valid_cf(), [2024])
    assert any(e.line_item == "Gross Profit" for e in errors)


def test_rule4_ebit_mismatch():
    pnl = _valid_pnl()
    pnl["EBIT"][2024] = Decimal("0")  # Wrong: should be 390
    errors = validate_historical_data(pnl, _valid_bs(), _valid_cf(), [2024])
    assert any(e.line_item == "EBIT" for e in errors)


def test_rule6_net_income_mismatch():
    pnl = _valid_pnl()
    pnl["Net Income"][2024] = Decimal("0")
    errors = validate_historical_data(pnl, _valid_bs(), _valid_cf(), [2024])
    assert any(e.line_item == "Net Income" for e in errors)


def test_rule1_balance_sheet_imbalance():
    bs = _valid_bs()
    bs["Cash & Equivalents"][2024] = Decimal("9999")  # Break the balance
    errors = validate_historical_data(_valid_pnl(), bs, _valid_cf(), [2024])
    assert any(e.tab == "Balance Sheet" and "Total Assets" in e.line_item for e in errors)


def test_rule7_missing_required_pnl_field():
    pnl = _valid_pnl()
    del pnl["Tax"]
    errors = validate_historical_data(pnl, _valid_bs(), _valid_cf(), [2024])
    assert any(e.line_item == "Tax" for e in errors)


def test_rule2_cash_reconciliation_across_years():
    pnl = {**_valid_pnl(2023), **{k: {**v, 2024: v[2023]} for k, v in _valid_pnl(2023).items()}}
    bs_2023 = _valid_bs(2023)
    bs_2024 = _valid_bs(2024)
    # Shift cash so Cash(2024) ≠ Cash(2023) + Net Change
    bs_2024["Cash & Equivalents"][2024] = Decimal("500")
    # Re-balance 2024 to isolate rule 2 from rule 1
    bs_2024["Retained Earnings"][2024] = Decimal("-540")
    bs_merged = {k: {**bs_2023[k], **bs_2024[k]} for k in bs_2023}
    cf = {"Net Change in Cash": {2024: Decimal("10")}}  # Expected cash = 210, actual = 500
    errors = validate_historical_data(pnl, bs_merged, cf, [2023, 2024])
    assert any(e.line_item == "Net Change in Cash" for e in errors)
