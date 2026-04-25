"""Balance-sheet rollforwards.

Covers steps 4 (PP&E + D&A), 5 (Intangibles + Amortization),
7 (Debt + Interest Expense), 15 (Retained Earnings), 16 (Equity),
17 (Working Capital), 20 (Non-Op Assets / Goodwill / Other LT Liab).
Some of these write a P&L number as a side-effect (D&A, Amortization,
Interest Expense) — they live here because the driver is a BS rollforward.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Dict

from app.services.utils import ZERO, d


class _BalanceSheetMixin:
    # ------------------------------------------------------------------
    # Step 4: PP&E roll-forward → D&A
    # ------------------------------------------------------------------
    def _compute_ppe_and_da(self, year: int, year_idx: int):
        self.pnl.setdefault(year, {})
        self.bs.setdefault(year, {})
        prev_year = self._prev_year(year)
        da_cfg = self.assumptions.get("da", {})
        capex_cfg = self.assumptions.get("capex", {})

        capex = self._compute_capex_value(year, year_idx, capex_cfg)
        self.bs[year]["_capex"] = capex

        ppe_gross_prev = self._get_bs("PP&E Gross", prev_year) if prev_year else ZERO
        ppe_gross = ppe_gross_prev + capex
        self.bs[year]["PP&E Gross"] = ppe_gross

        dep_cfg = da_cfg.get("depreciation", {})
        dep_method = dep_cfg.get("method", "pct_gross_ppe")

        if dep_method == "pct_gross_ppe":
            pct = self._param(dep_cfg, "pct", year) or ZERO
            da = ppe_gross * pct / 100
        elif dep_method == "fixed":
            da = self._param(dep_cfg, "value", year) or ZERO
        elif dep_method == "schedule":
            da = self._param(dep_cfg, "value", year) or ZERO
        else:
            da = self._last_hist("PNL", "D&A")

        acc_dep_prev = self._get_bs("Accumulated Depreciation", prev_year) if prev_year else ZERO
        acc_dep = acc_dep_prev + da
        self.bs[year]["Accumulated Depreciation"] = acc_dep
        self.bs[year]["Net PP&E"] = ppe_gross - acc_dep
        self.pnl[year]["D&A"] = da

    def _compute_capex_value(self, year: int, year_idx: int, capex_cfg: Dict) -> Decimal:
        method = capex_cfg.get("projection_method", "pct_revenue")
        revenue = self._proj_pnl("Revenue", year)

        if method == "pct_revenue":
            pct = self._param(capex_cfg, "pct", year) or ZERO
            return revenue * pct / 100
        elif method == "pct_net_ppe":
            prev_year = self._prev_year(year)
            net_ppe = self._get_bs("Net PP&E", prev_year) if prev_year else ZERO
            pct = self._param(capex_cfg, "pct", year) or ZERO
            return net_ppe * pct / 100
        elif method == "fixed":
            return self._param(capex_cfg, "value", year) or ZERO
        elif method == "manual":
            return self._param(capex_cfg, "value", year) or ZERO
        elif method == "maintenance_growth":
            maint_pct = self._param(capex_cfg, "maintenance_pct", year) or ZERO
            growth_val = self._param(capex_cfg, "growth_value", year) or ZERO
            return revenue * maint_pct / 100 + growth_val
        return ZERO

    # ------------------------------------------------------------------
    # Step 5: Intangibles roll-forward → Amortization
    # ------------------------------------------------------------------
    def _compute_intangibles(self, year: int, year_idx: int):
        self.bs.setdefault(year, {})
        self.pnl.setdefault(year, {})
        prev_year = self._prev_year(year)
        da_cfg = self.assumptions.get("da", {})
        amort_cfg = da_cfg.get("amortization", {})

        intangibles_gross_prev = self._get_bs("Intangibles Gross", prev_year) if prev_year else ZERO
        self.bs[year]["Intangibles Gross"] = intangibles_gross_prev

        amort_method = amort_cfg.get("method", "pct_gross")
        if amort_method == "pct_gross":
            pct = self._param(amort_cfg, "pct", year) or ZERO
            amort = intangibles_gross_prev * pct / 100
        elif amort_method == "fixed":
            amort = self._param(amort_cfg, "value", year) or ZERO
        elif amort_method == "straight_line":
            useful_life_years = self._param(amort_cfg, "useful_life_years", year) or Decimal("1")
            amort = intangibles_gross_prev / useful_life_years if useful_life_years != 0 else ZERO
        else:
            amort = ZERO

        acc_amort_prev = self._get_bs("Accumulated Amortization", prev_year) if prev_year else ZERO
        # Clamp amortization so Net Intangibles doesn't go below zero
        remaining = max(ZERO, intangibles_gross_prev - acc_amort_prev)
        amort = min(amort, remaining)
        acc_amort = acc_amort_prev + amort
        self.bs[year]["Accumulated Amortization"] = acc_amort
        self.bs[year]["Net Intangibles"] = max(ZERO, intangibles_gross_prev - acc_amort)
        self.pnl[year]["Amortization of Intangibles"] = amort

    # ------------------------------------------------------------------
    # Step 7: Debt roll-forward → Interest Expense (beginning-of-period)
    # ------------------------------------------------------------------
    def _compute_debt_and_interest(self, year: int, year_idx: int):
        self.pnl.setdefault(year, {})
        self.bs.setdefault(year, {})
        prev_year = self._prev_year(year)
        debt_cfg = self.assumptions.get("debt", {})

        st_debt_prev = self._get_bs("Short-Term Debt", prev_year) if prev_year else ZERO
        lt_debt_prev = self._get_bs("Long-Term Debt", prev_year) if prev_year else ZERO
        total_debt_prev = st_debt_prev + lt_debt_prev

        rate_cfg = debt_cfg.get("interest_rate", {})
        rate_method = rate_cfg.get("method", "fixed")
        if rate_method == "fixed":
            rate = self._param(rate_cfg, "rate", year) or ZERO
        elif rate_method == "variable":
            rate = self._param(rate_cfg, "rate", year) or ZERO
        elif rate_method == "base_spread":
            base = self._param(rate_cfg, "base_rate", year) or ZERO
            spread = self._param(rate_cfg, "spread_bps", year) or ZERO
            rate = base + spread / 10000
        else:
            rate = ZERO

        # Interest Expense on beginning-of-period balance (no circularity)
        self.pnl[year]["Interest Expense"] = total_debt_prev * rate / 100

        new_debt = self._param(debt_cfg, "new_debt", year) or ZERO
        amortization = self._param(debt_cfg, "repayment", year) or ZERO
        existing_repayment = self._param(debt_cfg.get("existing_debt", {}), "repayment", year) or ZERO
        total_repayment = amortization + existing_repayment

        new_total_debt = total_debt_prev + new_debt - total_repayment
        new_total_debt = max(ZERO, new_total_debt)

        self.bs[year]["Long-Term Debt"] = new_total_debt
        self.bs[year]["Short-Term Debt"] = ZERO
        self.bs[year]["_debt_issuance"] = new_debt
        self.bs[year]["_debt_repayment"] = total_repayment

    # ------------------------------------------------------------------
    # Step 15: Retained Earnings
    # ------------------------------------------------------------------
    def _compute_retained_earnings(self, year: int, dividends: Decimal):
        self.bs.setdefault(year, {})
        prev_year = self._prev_year(year)
        re_prev = self._get_bs("Retained Earnings", prev_year) if prev_year else ZERO
        ni = self._proj_pnl("Net Income", year)
        self.bs[year]["Retained Earnings"] = re_prev + ni - dividends

    # ------------------------------------------------------------------
    # Step 16: Equity changes
    # ------------------------------------------------------------------
    def _compute_equity(self, year: int):
        self.bs.setdefault(year, {})
        prev_year = self._prev_year(year)
        nonop_cfg = self.assumptions.get("non_operating", {})
        equity_cfg = nonop_cfg.get("equity", {})
        method = equity_cfg.get("method", "flat")

        sc_prev = self._get_bs("Share Capital", prev_year) if prev_year else ZERO
        oe_prev = self._get_bs("Other Equity (AOCI, Treasury Stock, etc.)", prev_year) if prev_year else ZERO

        if method == "flat":
            self.bs[year]["Share Capital"] = sc_prev
            self.bs[year]["Other Equity (AOCI, Treasury Stock, etc.)"] = oe_prev
            issuance = ZERO
            buyback = ZERO
        elif method == "issuance_schedule":
            issuance = self._param(equity_cfg, "issuance", year) or ZERO
            self.bs[year]["Share Capital"] = sc_prev + issuance
            self.bs[year]["Other Equity (AOCI, Treasury Stock, etc.)"] = oe_prev
            buyback = ZERO
        elif method == "buyback_schedule":
            buyback = self._param(equity_cfg, "buyback", year) or ZERO
            self.bs[year]["Share Capital"] = sc_prev
            self.bs[year]["Other Equity (AOCI, Treasury Stock, etc.)"] = oe_prev - buyback
            issuance = ZERO
        else:
            self.bs[year]["Share Capital"] = sc_prev
            self.bs[year]["Other Equity (AOCI, Treasury Stock, etc.)"] = oe_prev
            issuance = ZERO
            buyback = ZERO

        self.bs[year]["_equity_issuance"] = issuance
        self.bs[year]["_equity_buyback"] = buyback

    # ------------------------------------------------------------------
    # Step 17: Working Capital
    # ------------------------------------------------------------------
    def _compute_working_capital(self, year: int, year_idx: int):
        self.bs.setdefault(year, {})
        prev_year = self._prev_year(year)
        wc_cfg = self.assumptions.get("working_capital", {})
        revenue = self._proj_pnl("Revenue", year)
        cogs = self._proj_pnl("Cost of Goods Sold", year)

        def compute_wc_item(li: str, cfg: Dict) -> Decimal:
            method = cfg.get("method", "flat")
            prev_val = self._get_bs(li, prev_year) if prev_year else ZERO

            if method == "dio":  # Days Inventory Outstanding
                days = self._param(cfg, "days", year) or ZERO
                return (cogs / 365) * days if cogs else ZERO
            elif method == "dso":  # Days Sales Outstanding
                days = self._param(cfg, "days", year) or ZERO
                return (revenue / 365) * days if revenue else ZERO
            elif method == "dpo":  # Days Payable Outstanding
                days = self._param(cfg, "days", year) or ZERO
                return (cogs / 365) * days if cogs else ZERO
            elif method == "pct_revenue":
                pct = self._param(cfg, "pct", year) or ZERO
                return revenue * pct / 100
            elif method == "pct_cogs":
                pct = self._param(cfg, "pct", year) or ZERO
                return cogs * pct / 100
            elif method == "pct_opex":
                total_opex = sum(d(self.pnl[year].get(li2, ZERO)) for li2 in ["SG&A", "R&D", "Other OpEx"])
                pct = self._param(cfg, "pct", year) or ZERO
                return total_opex * pct / 100
            elif method == "fixed":
                return self._param(cfg, "value", year) or prev_val
            elif method == "flat":
                return prev_val
            else:
                return prev_val

        wc_items = {
            "Inventories": wc_cfg.get("inventories", {"method": "flat"}),
            "Accounts Receivable": wc_cfg.get("accounts_receivable", {"method": "flat"}),
            "Prepaid Expenses & Other Current Assets": wc_cfg.get("prepaid", {"method": "flat"}),
            "Accounts Payable": wc_cfg.get("accounts_payable", {"method": "flat"}),
            "Accrued Liabilities": wc_cfg.get("accrued_liabilities", {"method": "flat"}),
            "Other Current Liabilities": wc_cfg.get("other_current_liabilities", {"method": "flat"}),
        }

        for li, cfg in wc_items.items():
            self.bs[year][li] = compute_wc_item(li, cfg)

    # ------------------------------------------------------------------
    # Step 20: Non-Operating Assets, Goodwill, Other LT Liabilities
    # ------------------------------------------------------------------
    def _compute_nonop_assets(self, year: int):
        self.bs.setdefault(year, {})
        prev_year = self._prev_year(year)
        nonop_cfg = self.assumptions.get("non_operating", {})

        noa_cfg = nonop_cfg.get("non_operating_assets", {"method": "flat"})
        noa_prev = self._get_bs("Non-Operating Assets", prev_year) if prev_year else ZERO
        noa_method = noa_cfg.get("method", "flat")
        if noa_method == "flat":
            self.bs[year]["Non-Operating Assets"] = noa_prev
        elif noa_method == "fixed":
            self.bs[year]["Non-Operating Assets"] = self._param(noa_cfg, "value", year) or noa_prev
        elif noa_method in ("growth_flat", "growth_variable"):
            rate = self._param(noa_cfg, "growth_rate", year) or ZERO
            self.bs[year]["Non-Operating Assets"] = noa_prev * (1 + rate / 100)
        else:
            self.bs[year]["Non-Operating Assets"] = noa_prev

        goodwill_prev = self._get_bs("Goodwill", prev_year) if prev_year else ZERO
        self.bs[year]["Goodwill"] = goodwill_prev

        olt_prev = self._get_bs("Other Long-Term Liabilities", prev_year) if prev_year else ZERO
        self.bs[year]["Other Long-Term Liabilities"] = olt_prev
