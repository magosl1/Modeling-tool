from decimal import Decimal
from app.services.projection_engine import ProjectionEngine, ProjectionResult

def test_projection_balance():
    # Setup sample data
    hist_pnl = {
        "Revenue": {2023: Decimal("1000")},
        "Cost of Goods Sold": {2023: Decimal("600")},
        "Gross Profit": {2023: Decimal("400")},
        "SG&A": {2023: Decimal("100")},
        "R&D": {2023: Decimal("50")},
        "D&A": {2023: Decimal("20")},
        "Amortization of Intangibles": {2023: Decimal("0")},
        "Other OpEx": {2023: Decimal("10")},
        "EBIT": {2023: Decimal("220")},
        "Interest Income": {2023: Decimal("5")},
        "Interest Expense": {2023: Decimal("15")},
        "Other Non-Operating Income / (Expense)": {2023: Decimal("5")},
        "EBT": {2023: Decimal("205")},
        "Tax": {2023: Decimal("41")},
        "Net Income": {2023: Decimal("164")},
    }
    
    hist_bs = {
        "PP&E Gross": {2023: Decimal("500")},
        "Accumulated Depreciation": {2023: Decimal("100")},
        "Net PP&E": {2023: Decimal("400")},
        "Intangibles Gross": {2023: Decimal("50")},
        "Accumulated Amortization": {2023: Decimal("10")},
        "Net Intangibles": {2023: Decimal("40")},
        "Goodwill": {2023: Decimal("20")},
        "Inventories": {2023: Decimal("100")},
        "Accounts Receivable": {2023: Decimal("150")},
        "Prepaid Expenses & Other Current Assets": {2023: Decimal("30")},
        "Cash & Equivalents": {2023: Decimal("200")},
        "Non-Operating Assets": {2023: Decimal("50")},
        "Accounts Payable": {2023: Decimal("80")},
        "Accrued Liabilities": {2023: Decimal("40")},
        "Other Current Liabilities": {2023: Decimal("20")},
        "Other Long-Term Liabilities": {2023: Decimal("150")},
        "Short-Term Debt": {2023: Decimal("50")},
        "Long-Term Debt": {2023: Decimal("200")},
        "Share Capital": {2023: Decimal("300")},
        "Retained Earnings": {2023: Decimal("100")},
        "Other Equity (AOCI, Treasury Stock, etc.)": {2023: Decimal("50")},
    }
    
    # Verify 2023 balances (Absolute values)
    # Assets: Net PPE (400) + Net Intang (40) + Goodwill (20) + Inv (100) + AR (150) + Pre (30) + Cash (200) + NOA (50) = 990
    # L+E: AP (80) + Accrued (40) + OCL (20) + OLT (150) + Debt (50+200) + Equity (300 + 100 + 50) = 990
    # Sum: Assets - L+E = 0. OK.

    hist_cf = {
        "Net Change in Cash": {2023: Decimal("50")} # This doesn't matter for 2024 projection
    }
    
    assumptions = {
        "revenue": {"streams": [{"projection_method": "growth_flat", "params": [{"param_key": "growth_rate", "year": 2024, "value": Decimal("10")}]}]},
        "cogs": {"projection_method": "pct_revenue", "params": [{"param_key": "pct", "year": 2024, "value": Decimal("60")}]},
        "tax": {"projection_method": "single_rate", "params": [{"param_key": "rate", "year": 2024, "value": Decimal("20")}]},
    }
    
    engine = ProjectionEngine(
        historical_pnl=hist_pnl,
        historical_bs=hist_bs,
        historical_cf=hist_cf,
        historical_years=[2023],
        projection_years=[2024],
        assumptions=assumptions
    )
    
    result = engine.run()
    
    print("\n--- 2024 P&L ---")
    for li, years in result.pnl.items():
        print(f"{li}: {years.get(2024)}")
        
    print("\n--- 2024 BS ---")
    bs24 = {li: years.get(2024) for li, years in result.bs.items()}
    for li, val in bs24.items():
        print(f"{li}: {val}")

    assets = abs(bs24.get("Net PP&E", 0)) + abs(bs24.get("Net Intangibles", 0)) + \
             abs(bs24.get("Goodwill", 0)) + abs(bs24.get("Inventories", 0)) + \
             abs(bs24.get("Accounts Receivable", 0)) + abs(bs24.get("Prepaid Expenses & Other Current Assets", 0)) + \
             abs(bs24.get("Cash & Equivalents", 0)) + abs(bs24.get("Non-Operating Assets", 0))
    
    liabs = abs(bs24.get("Accounts Payable", 0)) + abs(bs24.get("Accrued Liabilities", 0)) + \
            abs(bs24.get("Other Current Liabilities", 0)) + abs(bs24.get("Other Long-Term Liabilities", 0)) + \
            abs(bs24.get("Short-Term Debt", 0)) + abs(bs24.get("Long-Term Debt", 0))
    
    equity = abs(bs24.get("Share Capital", 0)) + abs(bs24.get("Retained Earnings", 0)) + \
             abs(bs24.get("Other Equity (AOCI, Treasury Stock, etc.)", 0))
             
    print(f"\nManual Asset Sum: {assets}")
    print(f"Manual Liab Sum: {liabs}")
    print(f"Manual Equity Sum: {equity}")
    print(f"Manual L+E Sum: {liabs + equity}")

    print(f"\nErrors: {result.errors}")
    print(f"Warnings: {result.warnings}")
    
    if result.errors:
        exit(1)
    
    # Check if Other Long-Term Liabilities is in 2024 BS
    olt_2024 = result.bs.get("Other Long-Term Liabilities", {}).get(2024)
    print(f"Other Long-Term Liabilities 2024: {olt_2024}")
    if olt_2024 != Decimal("150"):  # Absolute convention
        print("FAIL: Other Long-Term Liabilities not carried forward correctly")
        exit(1)

    print("SUCCESS: All checks passed")

if __name__ == "__main__":
    test_projection_balance()
