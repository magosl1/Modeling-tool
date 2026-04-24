"""Cash flow derivation and balance-sheet close.

Covers steps 18 (derived CF), 19 (Cash BS), 21 (BS validation).
"""
from __future__ import annotations

from decimal import Decimal

from app.services.utils import ZERO, d


class _CashFlowMixin:
    # ------------------------------------------------------------------
    # Step 18: Cash Flow (fully derived)
    # ------------------------------------------------------------------
    def _compute_cash_flow(self, year: int) -> Decimal:
        self.cf.setdefault(year, {})
        prev_year = self._prev_year(year)

        net_income = self._proj_pnl("Net Income", year)
        da = self._proj_pnl("D&A", year)
        amort = self._proj_pnl("Amortization of Intangibles", year)

        def delta(li: str) -> Decimal:
            curr = d(self.bs[year].get(li, ZERO))
            prev = self._get_bs(li, prev_year) if prev_year else ZERO
            return curr - prev

        d_inventories = delta("Inventories")
        d_ar = delta("Accounts Receivable")
        d_prepaid = delta("Prepaid Expenses & Other Current Assets")
        d_ap = delta("Accounts Payable")
        d_accrued = delta("Accrued Liabilities")
        d_ocl = delta("Other Current Liabilities")
        d_olt = delta("Other Long-Term Liabilities")

        changes_wc = -d_inventories - d_ar - d_prepaid + d_ap + d_accrued + d_ocl + d_olt

        ocf = net_income + da + amort + changes_wc
        self.cf[year]["Net Income"] = net_income
        self.cf[year]["D&A Add-back"] = da
        self.cf[year]["Amortization of Intangibles Add-back"] = amort
        self.cf[year]["Changes in Working Capital"] = changes_wc
        self.cf[year]["Operating Cash Flow"] = ocf

        capex = d(self.bs[year].get("_capex", ZERO))
        d_nonop = delta("Non-Operating Assets")
        icf = -capex - d_nonop
        self.cf[year]["Capex"] = -capex
        self.cf[year]["Acquisitions / Disposals"] = -d_nonop
        self.cf[year]["Investing Cash Flow"] = icf

        debt_issuance = d(self.bs[year].get("_debt_issuance", ZERO))
        debt_repayment = d(self.bs[year].get("_debt_repayment", ZERO))
        dividends = d(self.pnl[year].get("_dividends", ZERO))
        equity_issuance = d(self.bs[year].get("_equity_issuance", ZERO))
        equity_buyback = d(self.bs[year].get("_equity_buyback", ZERO))

        fcf_fin = debt_issuance - debt_repayment - dividends + equity_issuance - equity_buyback
        self.cf[year]["Debt Issuance / Repayment"] = debt_issuance - debt_repayment
        self.cf[year]["Dividends Paid"] = -dividends
        self.cf[year]["Share Issuance / Buyback"] = equity_issuance - equity_buyback
        self.cf[year]["Financing Cash Flow"] = fcf_fin

        net_change = ocf + icf + fcf_fin
        self.cf[year]["Net Change in Cash"] = net_change

        return net_change

    # ------------------------------------------------------------------
    # Step 19: Cash (BS)
    # ------------------------------------------------------------------
    def _compute_cash_bs(self, year: int, net_change: Decimal) -> Decimal:
        self.bs.setdefault(year, {})
        prev_year = self._prev_year(year)
        cash_prev = self._get_bs("Cash & Equivalents", prev_year) if prev_year else ZERO
        cash = cash_prev + net_change
        self.bs[year]["Cash & Equivalents"] = cash
        if cash < ZERO:
            self.result.warnings.append(
                f"Year {year}: Negative cash balance ({cash}). Consider revising assumptions."
            )
        return cash

    # ------------------------------------------------------------------
    # Step 21: Balance Sheet validation
    # ------------------------------------------------------------------
    def _validate_balance_sheet(self, year: int):
        bs = self.bs[year]
        net_ppe = d(bs.get("Net PP&E", ZERO))
        net_intang = d(bs.get("Net Intangibles", ZERO))
        goodwill = d(bs.get("Goodwill", ZERO))
        inventories = d(bs.get("Inventories", ZERO))
        ar = d(bs.get("Accounts Receivable", ZERO))
        prepaid = d(bs.get("Prepaid Expenses & Other Current Assets", ZERO))
        cash = d(bs.get("Cash & Equivalents", ZERO))
        noa = d(bs.get("Non-Operating Assets", ZERO))

        total_assets = (
            max(ZERO, net_ppe) + max(ZERO, net_intang) + max(ZERO, goodwill) +
            max(ZERO, inventories) + max(ZERO, ar) + max(ZERO, prepaid) +
            max(ZERO, cash) + max(ZERO, noa)
        )

        ap = d(bs.get("Accounts Payable", ZERO))
        accrued = d(bs.get("Accrued Liabilities", ZERO))
        ocl = d(bs.get("Other Current Liabilities", ZERO))
        other_lt = d(bs.get("Other Long-Term Liabilities", ZERO))
        st_debt = d(bs.get("Short-Term Debt", ZERO))
        lt_debt = d(bs.get("Long-Term Debt", ZERO))
        total_liabilities = (
            abs(ap) + abs(accrued) + abs(ocl) + abs(other_lt) + abs(st_debt) + abs(lt_debt)
        )

        sc = d(bs.get("Share Capital", ZERO))
        re = d(bs.get("Retained Earnings", ZERO))
        oe = d(bs.get("Other Equity (AOCI, Treasury Stock, etc.)", ZERO))
        total_equity = abs(sc) + abs(re) + abs(oe)

        total_le = total_liabilities + total_equity
        residual = total_assets - total_le

        tolerance = max(Decimal("1"), total_assets * Decimal("0.005"))
        if abs(residual) > tolerance:
            self.result.errors.append(
                f"Year {year}: Balance Sheet doesn't balance. "
                f"Assets={total_assets}, L+E={total_le}, Residual={residual}. "
                "Check Working Capital, Debt, and Equity assumptions."
            )
        if total_equity < ZERO:
            self.result.warnings.append(f"Year {year}: Negative equity ({total_equity}).")

        self.bs[year]["_total_assets"] = total_assets
        self.bs[year]["_total_liabilities"] = total_liabilities
        self.bs[year]["_total_equity"] = total_equity
