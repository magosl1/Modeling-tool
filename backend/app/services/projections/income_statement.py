"""Income statement computations (P&L-driving steps of the 21-step compile).

Covers: Revenue (1), COGS (2), OpEx (3), EBIT (6), Interest Income (8),
Other Non-Op (9), EBT (10), Tax + NOL (11-12), Net Income (13),
Dividends (14). Steps that write a P&L number as a side-effect of a
balance-sheet rollforward (D&A from PP&E, Amortization from Intangibles,
Interest Expense from Debt) live in `balance_sheet.py`.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Dict

from app.services.utils import ZERO, d


class _IncomeStatementMixin:
    # ------------------------------------------------------------------
    # Step 1: Revenue
    # ------------------------------------------------------------------
    def _compute_revenue(self, year: int, year_idx: int):
        self.pnl.setdefault(year, {})
        revenue_cfg = self.assumptions.get("revenue", {})
        streams = revenue_cfg.get("streams", [])

        if not streams:
            # Fallback: flat from last historical
            base = self._last_hist("PNL", "Revenue")
            self.pnl[year]["Revenue"] = base
            return

        total_revenue = ZERO
        for stream in streams:
            method = stream.get("projection_method", "growth_flat")
            stream_name = stream.get("stream_name", "Revenue")

            if year_idx == 0:
                base = d(self.hist_pnl.get(stream_name, {}).get(self.last_hist_year))
                if base == ZERO:
                    base = self._last_hist("PNL", "Revenue")
            else:
                prev = self.proj_years[year_idx - 1]
                base = d(self.pnl[prev].get(f"_rev_{stream_name}", ZERO))

            if method in ("growth_flat", "growth_variable"):
                base_override = self._param(stream, "base_value", year)
                if base_override is not None:
                    base = d(base_override)
                rate = self._param(stream, "growth_rate", year) or ZERO
                val = base * (1 + rate / 100)
            elif method == "price_quantity":
                price_cfg = stream.get("price", {})
                qty_cfg = stream.get("quantity", {})
                price_base = d(self.hist_pnl.get(f"{stream_name}_price", {}).get(self.last_hist_year, 1))
                qty_base = d(self.hist_pnl.get(f"{stream_name}_quantity", {}).get(self.last_hist_year, base))

                if year_idx > 0:
                    prev = self.proj_years[year_idx - 1]
                    price_base = d(self.pnl[prev].get(f"_price_{stream_name}", price_base))
                    qty_base = d(self.pnl[prev].get(f"_qty_{stream_name}", qty_base))

                price_method = price_cfg.get("method", "growth_flat")
                if price_method == "growth_flat":
                    rate = d(price_cfg.get("growth_rate", 0))
                    price = price_base * (1 + rate / 100)
                elif price_method == "fixed":
                    price = d(price_cfg.get("value", {}).get(str(year), price_base))
                else:
                    price = price_base

                qty_method = qty_cfg.get("method", "growth_flat")
                if qty_method == "growth_flat":
                    rate = d(qty_cfg.get("growth_rate", 0))
                    qty = qty_base * (1 + rate / 100)
                elif qty_method == "fixed":
                    qty = d(qty_cfg.get("value", {}).get(str(year), qty_base))
                else:
                    qty = qty_base

                self.pnl[year][f"_price_{stream_name}"] = price
                self.pnl[year][f"_qty_{stream_name}"] = qty
                val = price * qty
            elif method == "fixed":
                val = self._param(stream, "value", year) or base
            elif method == "external_curve":
                val = self._param(stream, "value", year) or base
            else:
                val = base

            self.pnl[year][f"_rev_{stream_name}"] = val
            total_revenue += val

        self.pnl[year]["Revenue"] = total_revenue

    # ------------------------------------------------------------------
    # Step 2: COGS → Gross Profit
    # ------------------------------------------------------------------
    def _compute_cogs(self, year: int, year_idx: int):
        self.pnl.setdefault(year, {})
        cogs_cfg = self.assumptions.get("cogs", {})
        method = cogs_cfg.get("projection_method", "pct_revenue")
        revenue = self._proj_pnl("Revenue", year)

        if method == "pct_revenue":
            pct = self._param(cogs_cfg, "pct", year) or ZERO
            cogs = revenue * pct / 100
        elif method == "gross_margin_pct":
            gm_pct = self._param(cogs_cfg, "gm_pct", year) or ZERO
            cogs = revenue * (1 - gm_pct / 100)
        elif method == "fixed":
            cogs = self._param(cogs_cfg, "value", year) or self._last_hist("PNL", "Cost of Goods Sold")
        elif method == "variable_fixed":
            var_pct = self._param(cogs_cfg, "variable_pct", year) or ZERO
            var_component = revenue * var_pct / 100
            fixed_method = cogs_cfg.get("fixed_method", "fixed")
            if fixed_method == "fixed":
                fixed_component = self._param(cogs_cfg, "fixed_value", year) or ZERO
            else:
                base = self._last_hist("PNL", "Cost of Goods Sold") * (1 - (self._param(cogs_cfg, "variable_pct", year) or ZERO) / 100)
                rate = self._param(cogs_cfg, "fixed_growth_rate", year) or ZERO
                fixed_component = base * (1 + rate / 100)
            cogs = var_component + fixed_component
        else:
            cogs = self._last_hist("PNL", "Cost of Goods Sold")

        self.pnl[year]["Cost of Goods Sold"] = cogs
        self.pnl[year]["Gross Profit"] = revenue - cogs

    # ------------------------------------------------------------------
    # Step 3: OpEx
    # ------------------------------------------------------------------
    def _compute_opex(self, year: int, year_idx: int):
        self.pnl.setdefault(year, {})
        opex_cfg = self.assumptions.get("opex", {})
        items = opex_cfg.get("items", [{"line_item": "SG&A", "projection_method": "pct_revenue"},
                                        {"line_item": "R&D", "projection_method": "pct_revenue"},
                                        {"line_item": "Other OpEx", "projection_method": "pct_revenue"}])
        revenue = self._proj_pnl("Revenue", year)
        cogs = self._proj_pnl("Cost of Goods Sold", year)

        for item_cfg in items:
            li = item_cfg.get("line_item", "SG&A")
            method = item_cfg.get("projection_method", "pct_revenue")

            if year_idx == 0:
                base = self._last_hist("PNL", li)
            else:
                prev = self.proj_years[year_idx - 1]
                base = d(self.pnl[prev].get(li, ZERO))

            if method == "pct_revenue":
                pct = self._param(item_cfg, "pct", year) or ZERO
                val = revenue * pct / 100
            elif method == "pct_cogs":
                pct = self._param(item_cfg, "pct", year) or ZERO
                val = cogs * pct / 100
            elif method == "growth_flat" or method == "growth_variable":
                rate = self._param(item_cfg, "growth_rate", year) or ZERO
                val = base * (1 + rate / 100)
            elif method == "fixed":
                val = self._param(item_cfg, "value", year) or base
            elif method == "flat":
                val = base
            elif method == "headcount":
                headcount = self._param(item_cfg, "headcount", year) or ZERO
                avg_cost = self._param(item_cfg, "avg_cost", year) or ZERO
                val = headcount * avg_cost
            else:
                val = base

            self.pnl[year][li] = val

        # Ensure SG&A, R&D, Other OpEx defaults
        for default_li in ["SG&A", "R&D", "D&A", "Amortization of Intangibles", "Other OpEx"]:
            if default_li not in self.pnl[year]:
                self.pnl[year][default_li] = ZERO

    # ------------------------------------------------------------------
    # Step 6: EBIT
    # ------------------------------------------------------------------
    def _compute_ebit(self, year: int):
        self.pnl.setdefault(year, {})
        gp = self._proj_pnl("Gross Profit", year)
        sga = self._proj_pnl("SG&A", year)
        rd = self._proj_pnl("R&D", year)
        da = self._proj_pnl("D&A", year)
        amort = self._proj_pnl("Amortization of Intangibles", year)
        other_opex = self._proj_pnl("Other OpEx", year)
        ebit = gp - sga - rd - da - amort - other_opex
        self.pnl[year]["EBIT"] = ebit
        self.pnl[year]["EBITDA"] = ebit + da + amort

    # ------------------------------------------------------------------
    # Step 8: Interest Income
    # ------------------------------------------------------------------
    def _compute_interest_income(self, year: int, year_idx: int):
        self.pnl.setdefault(year, {})
        prev_year = self._prev_year(year)
        ii_cfg = self.assumptions.get("interest_income", {})
        method = ii_cfg.get("projection_method", "zero")

        if method == "yield_on_cash":
            yield_pct = self._param(ii_cfg, "yield_pct", year) or ZERO
            cash_prev = self._get_bs("Cash & Equivalents", prev_year) if prev_year else ZERO
            self.pnl[year]["Interest Income"] = cash_prev * yield_pct / 100
        elif method == "fixed":
            self.pnl[year]["Interest Income"] = self._param(ii_cfg, "value", year) or ZERO
        else:
            self.pnl[year]["Interest Income"] = ZERO

    # ------------------------------------------------------------------
    # Step 9: Other Non-Operating
    # ------------------------------------------------------------------
    def _compute_other_nonop(self, year: int):
        self.pnl.setdefault(year, {})
        nonop_cfg = self.assumptions.get("non_operating", {})
        pl_cfg = nonop_cfg.get("other_nonop_pl", {})
        method = pl_cfg.get("method", "zero")

        if method == "zero":
            val = ZERO
        elif method == "fixed":
            val = self._param(pl_cfg, "value", year) or ZERO
        elif method == "flat":
            val = self._last_hist("PNL", "Other Non-Operating Income / (Expense)")
        else:
            val = ZERO
        self.pnl[year]["Other Non-Operating Income / (Expense)"] = val

    # ------------------------------------------------------------------
    # Step 10: EBT
    # ------------------------------------------------------------------
    def _compute_ebt(self, year: int):
        self.pnl.setdefault(year, {})
        ebit = self._proj_pnl("EBIT", year)
        ii = self._proj_pnl("Interest Income", year)
        ie = self._proj_pnl("Interest Expense", year)
        other = self._proj_pnl("Other Non-Operating Income / (Expense)", year)
        # Interest Expense is stored as a positive amount and must be subtracted from EBIT.
        # Interest Income and Other Non-Operating are positive and added.
        self.pnl[year]["EBT"] = ebit + ii - ie + other

    # ------------------------------------------------------------------
    # Step 11 + 12: NOL + Tax
    # ------------------------------------------------------------------
    def _compute_tax(self, year: int):
        self.pnl.setdefault(year, {})
        tax_cfg = self.assumptions.get("tax", {})
        method = tax_cfg.get("projection_method", "single_rate")
        enable_nol = tax_cfg.get("enable_nol_carryforward", False)

        if method == "single_rate":
            rate = self._param(tax_cfg, "rate", year) or ZERO
        elif method == "variable_rate":
            rate = self._param(tax_cfg, "rate", year) or ZERO
        else:
            rate = ZERO

        ebt = self._proj_pnl("EBT", year)

        # NOL carry-forward
        nol_used = ZERO
        if enable_nol and ebt > ZERO and self.nol_balance > ZERO:
            nol_used = min(self.nol_balance, ebt)
            ebt_after_nol = ebt - nol_used
        else:
            ebt_after_nol = ebt

        if ebt < ZERO:
            if enable_nol:
                self.nol_balance += abs(ebt)
            tax_val = ZERO
        else:
            tax_val = max(ZERO, ebt_after_nol * rate / 100)
            self.nol_balance -= nol_used

        self.pnl[year]["Tax"] = -tax_val  # Tax is an expense
        self.result.nol_balances[year] = {
            "nol_opening": self.nol_balance + (nol_used if ebt > ZERO else -abs(ebt) if enable_nol else ZERO),
            "nol_used": nol_used,
            "nol_closing": self.nol_balance,
        }

    # ------------------------------------------------------------------
    # Step 13: Net Income
    # ------------------------------------------------------------------
    def _compute_net_income(self, year: int):
        self.pnl.setdefault(year, {})
        ebt = self._proj_pnl("EBT", year)
        tax = self._proj_pnl("Tax", year)
        self.pnl[year]["Net Income"] = ebt + tax  # Tax is already negative

    # ------------------------------------------------------------------
    # Step 14: Dividends (returns value for use by RE step)
    # ------------------------------------------------------------------
    def _compute_dividends(self, year: int, year_idx: int) -> Decimal:
        self.pnl.setdefault(year, {})
        div_cfg = self.assumptions.get("dividends", {})
        method = div_cfg.get("projection_method", "zero")
        net_income = self._proj_pnl("Net Income", year)

        if method == "zero":
            dividends = ZERO
        elif method == "payout_ratio":
            payout = self._param(div_cfg, "payout_ratio", year) or ZERO
            dividends = max(ZERO, net_income) * payout / 100
        elif method == "fixed":
            dividends = self._param(div_cfg, "value", year) or ZERO
        elif method == "growth_rate":
            base = self._last_hist("PNL", "_dividends") if year_idx == 0 else d(self.pnl.get(self.proj_years[year_idx - 1], {}).get("_dividends", ZERO))
            rate = self._param(div_cfg, "growth_rate", year) or ZERO
            dividends = base * (1 + rate / 100)
        else:
            dividends = ZERO

        self.pnl[year]["_dividends"] = dividends
        return dividends
