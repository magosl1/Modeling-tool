"""Golden-snapshot test for ProjectionEngine.

Pre-refactor safety net: locks the *current* output of the 21-step compile
against a fixed input. Any behavior change shows up as a JSON diff.

The snapshot file is auto-created on first run (test fails with a hint),
and asserted against on every subsequent run. To intentionally update the
snapshot after a deliberate behavior change, delete the file and rerun.
"""
from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from app.services.projection_engine import ProjectionEngine, ProjectionResult

SNAPSHOT_PATH = Path(__file__).parent / "snapshots" / "projection_engine_v1.json"


def _hist() -> dict:
    """Minimal but complete historical dataset (year=2024)."""
    pnl = {
        "Revenue": {2024: Decimal("1000")},
        "Cost of Goods Sold": {2024: Decimal("400")},
        "SG&A": {2024: Decimal("150")},
        "R&D": {2024: Decimal("50")},
        "D&A": {2024: Decimal("80")},
        "Amortization of Intangibles": {2024: Decimal("20")},
        "Interest Expense": {2024: Decimal("30")},
        "Interest Income": {2024: Decimal("5")},
        "Other Non-Operating Income / (Expense)": {2024: Decimal("0")},
        "Tax Expense": {2024: Decimal("50")},
        "Net Income": {2024: Decimal("225")},
    }
    bs = {
        "Cash & Equivalents": {2024: Decimal("200")},
        "Accounts Receivable": {2024: Decimal("120")},
        "Inventories": {2024: Decimal("80")},
        "Prepaid Expenses & Other Current Assets": {2024: Decimal("10")},
        "Net PP&E": {2024: Decimal("600")},
        "Net Intangibles": {2024: Decimal("100")},
        "Goodwill": {2024: Decimal("50")},
        "Non-Operating Assets": {2024: Decimal("20")},
        "Accounts Payable": {2024: Decimal("90")},
        "Accrued Liabilities": {2024: Decimal("30")},
        "Other Current Liabilities": {2024: Decimal("10")},
        "Short-Term Debt": {2024: Decimal("50")},
        "Long-Term Debt": {2024: Decimal("300")},
        "Other Long-Term Liabilities": {2024: Decimal("20")},
        "Share Capital": {2024: Decimal("400")},
        "Retained Earnings": {2024: Decimal("280")},
        "Other Equity (AOCI, Treasury Stock, etc.)": {2024: Decimal("0")},
    }
    cf = {
        "Net Income": {2024: Decimal("225")},
        "D&A": {2024: Decimal("80")},
    }
    return pnl, bs, cf


def _assumptions() -> dict:
    """Cover every module the engine knows about with simple methods."""
    return {
        "revenue": {
            "streams": [
                {
                    "stream_name": "Revenue",
                    "projection_method": "growth_flat",
                    "params": [{"param_key": "growth_rate", "year": None, "value": Decimal("10")}],
                }
            ]
        },
        "cogs": {
            "projection_method": "pct_revenue",
            "params": [{"param_key": "pct", "year": None, "value": Decimal("40")}],
        },
        "opex": {
            "items": [
                {
                    "line_item": "SG&A",
                    "projection_method": "pct_revenue",
                    "params": [{"param_key": "pct", "year": None, "value": Decimal("15")}],
                },
                {
                    "line_item": "R&D",
                    "projection_method": "pct_revenue",
                    "params": [{"param_key": "pct", "year": None, "value": Decimal("5")}],
                },
            ]
        },
        "da": {
            "depreciation": {
                "method": "pct_revenue",
                "params": [{"param_key": "pct", "year": None, "value": Decimal("8")}],
            },
            "amortization": {
                "method": "fixed",
                "params": [{"param_key": "value", "year": None, "value": Decimal("20")}],
            },
        },
        "capex": {
            "projection_method": "pct_revenue",
            "params": [{"param_key": "pct", "year": None, "value": Decimal("10")}],
        },
        "working_capital": {
            "inventories": {
                "method": "flat",
                "params": [],
            },
            "accounts_receivable": {
                "method": "flat",
                "params": [],
            },
            "accounts_payable": {
                "method": "flat",
                "params": [],
            },
        },
        "debt": {
            "projection_method": "flat",
            "params": [],
            "interest_rate": {
                "method": "fixed",
                "params": [{"param_key": "rate", "year": None, "value": Decimal("8")}],
            },
        },
        "interest_income": {
            "projection_method": "fixed",
            "params": [{"param_key": "value", "year": None, "value": Decimal("5")}],
        },
        "tax": {
            "projection_method": "fixed",
            "params": [{"param_key": "value", "year": None, "value": Decimal("25")}],
        },
        "dividends": {
            "projection_method": "flat",
            "params": [],
        },
        "non_operating": {
            "non_operating_assets": {
                "method": "flat",
                "params": [],
            },
            "goodwill": {
                "method": "flat",
                "params": [],
            },
            "other_nonop_pl": {
                "method": "flat",
                "params": [],
            },
        },
    }


def _serialize(result: ProjectionResult) -> dict:
    """Canonical, JSON-friendly form. Decimals → strings to keep precision."""

    def _stmt(s):
        return {
            li: {str(yr): str(v.quantize(Decimal("0.0001"))) for yr, v in years.items()}
            for li, years in sorted(s.items())
        }

    return {
        "pnl": _stmt(result.pnl),
        "bs": _stmt(result.bs),
        "cf": _stmt(result.cf),
        "warnings": result.warnings,
        "errors": result.errors,
    }


def test_projection_engine_snapshot():
    pnl, bs, cf = _hist()
    engine = ProjectionEngine(
        historical_pnl=pnl,
        historical_bs=bs,
        historical_cf=cf,
        historical_years=[2024],
        projection_years=[2025, 2026],
        assumptions=_assumptions(),
    )
    actual = _serialize(engine.run())
    actual_text = json.dumps(actual, indent=2, sort_keys=True)

    if not SNAPSHOT_PATH.exists():
        SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT_PATH.write_text(actual_text + "\n")
        pytest.fail(
            f"Snapshot created at {SNAPSHOT_PATH}. "
            "Inspect it, commit it, and rerun the test."
        )

    expected_text = SNAPSHOT_PATH.read_text().rstrip("\n")
    assert actual_text == expected_text, (
        "ProjectionEngine output differs from snapshot. "
        "If this change is intentional, delete the snapshot file and rerun:\n"
        f"  rm {SNAPSHOT_PATH}"
    )
