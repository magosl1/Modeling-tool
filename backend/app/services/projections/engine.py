"""Orchestrator — composes the four mixins into the final ProjectionEngine.

The 21-step compile order lives here and only here. Each step delegates
to a mixin method whose implementation lives in its domain file.
"""
from __future__ import annotations

from app.services.projections._state import ProjectionResult, _EngineState
from app.services.projections.balance_sheet import _BalanceSheetMixin
from app.services.projections.cash_flow import _CashFlowMixin
from app.services.projections.income_statement import _IncomeStatementMixin


class ProjectionEngine(
    _IncomeStatementMixin,
    _BalanceSheetMixin,
    _CashFlowMixin,
    _EngineState,
):
    def run(self) -> ProjectionResult:
        for year_idx, year in enumerate(self.proj_years):
            # Steps 1–3: top of income statement
            self._compute_revenue(year, year_idx)
            self._compute_cogs(year, year_idx)
            self._compute_opex(year, year_idx)

            # Steps 4–5: PP&E + Intangibles (need to run before EBIT)
            self._compute_ppe_and_da(year, year_idx)
            self._compute_intangibles(year, year_idx)

            # Step 6: EBIT
            self._compute_ebit(year)

            # Steps 7–9: below-the-line income statement items
            self._compute_debt_and_interest(year, year_idx)
            self._compute_interest_income(year, year_idx)
            self._compute_other_nonop(year)

            # Step 10: EBT
            self._compute_ebt(year)

            # Steps 11–13: Tax + Net Income
            self._compute_tax(year)
            self._compute_net_income(year)

            # Step 14: Dividends
            dividends = self._compute_dividends(year, year_idx)

            # Step 15: Retained Earnings
            self._compute_retained_earnings(year, dividends)

            # Step 16: Equity changes
            self._compute_equity(year)

            # Step 17: Working Capital
            self._compute_working_capital(year, year_idx)

            # Step 20 — moved earlier so derived CF can use up-to-date values.
            # (Kept in original order for parity with pre-refactor behavior.)
            self._compute_nonop_assets(year)

            # Step 18: Cash Flow (derived)
            net_change = self._compute_cash_flow(year)

            # Step 19: Cash BS
            self._compute_cash_bs(year, net_change)

            # Step 21: Balance Sheet validation
            self._validate_balance_sheet(year)

        # Flatten per-year dicts into the ProjectionResult shape.
        for year in self.proj_years:
            for li, val in self.pnl.get(year, {}).items():
                if not li.startswith("_"):
                    self.result.pnl.setdefault(li, {})[year] = val
            for li, val in self.bs.get(year, {}).items():
                if not li.startswith("_"):
                    self.result.bs.setdefault(li, {})[year] = val
            for li, val in self.cf.get(year, {}).items():
                self.result.cf.setdefault(li, {})[year] = val

        return self.result
