"""
Generates Excel templates (historical data + module-specific) using openpyxl.
All templates: values only — no formulas, no formatting, no colors.
"""
from io import BytesIO
from typing import List
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter


PNL_ITEMS = [
    "Revenue",
    "Cost of Goods Sold",
    "Gross Profit",
    "SG&A",
    "R&D",
    "D&A",
    "Amortization of Intangibles",
    "Other OpEx",
    "EBIT",
    "Interest Income",
    "Interest Expense",
    "Other Non-Operating Income / (Expense)",
    "EBT",
    "Tax",
    "Net Income",
]

BS_ITEMS = [
    # Fixed Assets
    ("PP&E Gross", "Fixed Assets"),
    ("Accumulated Depreciation", "Fixed Assets"),
    ("Net PP&E", "Fixed Assets"),
    ("Intangibles Gross", "Fixed Assets"),
    ("Accumulated Amortization", "Fixed Assets"),
    ("Net Intangibles", "Fixed Assets"),
    ("Goodwill", "Fixed Assets"),
    # Working Capital
    ("Inventories", "Working Capital"),
    ("Accounts Receivable", "Working Capital"),
    ("Prepaid Expenses & Other Current Assets", "Working Capital"),
    ("Accounts Payable", "Working Capital"),
    ("Accrued Liabilities", "Working Capital"),
    ("Other Current Liabilities", "Working Capital"),
    # Cash
    ("Cash & Equivalents", "Cash"),
    # Non-Operating
    ("Non-Operating Assets", "Non-Operating"),
    # Debt
    ("Short-Term Debt", "Debt"),
    ("Long-Term Debt", "Debt"),
    # Equity
    ("Share Capital", "Equity"),
    ("Retained Earnings", "Equity"),
    ("Other Equity (AOCI, Treasury Stock, etc.)", "Equity"),
]

CF_ITEMS = [
    "Net Income",
    "D&A Add-back",
    "Amortization of Intangibles Add-back",
    "Changes in Working Capital",
    "Operating Cash Flow",
    "Capex",
    "Acquisitions / Disposals",
    "Investing Cash Flow",
    "Debt Issuance / Repayment",
    "Dividends Paid",
    "Share Issuance / Buyback",
    "Financing Cash Flow",
    "Net Change in Cash",
]


def _make_header_style():
    return Font(bold=True)


def _write_sheet(ws, items, years: List[int], units_label: str, include_bucket: bool = False):
    """Write a standardized financial data sheet."""
    headers = ["Line Item", "Units"] + [str(y) for y in years]
    if include_bucket:
        headers = ["Line Item", "Bucket", "Units"] + [str(y) for y in years]

    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = Font(bold=True)

    if include_bucket:
        for row_idx, (item, bucket) in enumerate(items, 2):
            ws.cell(row=row_idx, column=1, value=item)
            ws.cell(row=row_idx, column=2, value=bucket)
            ws.cell(row=row_idx, column=3, value=units_label)
    else:
        for row_idx, item in enumerate(items, 2):
            ws.cell(row=row_idx, column=1, value=item)
            ws.cell(row=row_idx, column=2, value=units_label)


def generate_historical_template(years: List[int], currency: str, scale: str) -> bytes:
    """Generate the 3-tab historical data Excel template."""
    units_label = f"{currency} {scale}"
    wb = openpyxl.Workbook()

    # Tab 1 — P&L
    ws_pnl = wb.active
    ws_pnl.title = "P&L"
    _write_sheet(ws_pnl, PNL_ITEMS, years, units_label)

    # Tab 2 — Balance Sheet
    ws_bs = wb.create_sheet("Balance Sheet")
    _write_sheet(ws_bs, BS_ITEMS, years, units_label, include_bucket=True)

    # Tab 3 — Cash Flow
    ws_cf = wb.create_sheet("Cash Flow")
    _write_sheet(ws_cf, CF_ITEMS, years, units_label)

    # Column widths
    for ws in [ws_pnl, ws_bs, ws_cf]:
        ws.column_dimensions["A"].width = 45
        ws.column_dimensions["B"].width = 20
        if ws == ws_bs:
            ws.column_dimensions["C"].width = 20
        for i, _ in enumerate(years):
            col_letter = get_column_letter(3 + i if ws != ws_bs else 4 + i)
            ws.column_dimensions[col_letter].width = 14

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def generate_module_template(
    module: str,
    line_items: List[str],
    years: List[int],
    currency: str,
    scale: str,
) -> bytes:
    """Generate a dynamic module template based on user configuration."""
    units_label = f"{currency} {scale}"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = module.upper()

    headers = ["Line Item", "Units"] + [str(y) for y in years]
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = Font(bold=True)

    for row_idx, item in enumerate(line_items, 2):
        ws.cell(row=row_idx, column=1, value=item)
        ws.cell(row=row_idx, column=2, value=units_label)

    ws.column_dimensions["A"].width = 45
    ws.column_dimensions["B"].width = 20
    for i, _ in enumerate(years):
        col_letter = get_column_letter(3 + i)
        ws.column_dimensions[col_letter].width = 14

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
