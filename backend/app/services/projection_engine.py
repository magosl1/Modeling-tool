"""
Projection Engine — 21-step compilation as specified.

Runs in strict dependency order:
 1.  Revenue
 2.  COGS → Gross Profit
 3.  OpEx
 4.  PP&E roll-forward → D&A
 5.  Intangibles roll-forward → Amortization
 6.  EBIT
 7.  Debt roll-forward → Interest Expense
 8.  Interest Income
 9.  Other Non-Operating
10.  EBT
11.  NOL carry-forward check
12.  Tax
13.  Net Income
14.  Dividends
15.  RE(t) = RE(t-1) + Net Income − Dividends
16.  Equity changes
17.  Working Capital
18.  Cash Flow (derived)
19.  Cash(BS) = Cash(t-1) + ΔCash
20.  Non-Operating Assets, Goodwill
21.  Balance Sheet close → validation
"""
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from app.services.utils import ZERO, d

TOLERANCE = Decimal("0.5")


@dataclass
class ProjectionResult:
    pnl: Dict[str, Dict[int, Decimal]] = field(default_factory=dict)
    bs: Dict[str, Dict[int, Decimal]] = field(default_factory=dict)
    cf: Dict[str, Dict[int, Decimal]] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    nol_balances: Dict[int, Dict[str, Decimal]] = field(default_factory=dict)


class ProjectionEngine:
    def __init__(
        self,
        historical_pnl: Dict[str, Dict[int, Decimal]],
        historical_bs: Dict[str, Dict[int, Decimal]],
        historical_cf: Dict[str, Dict[int, Decimal]],
        historical_years: List[int],
        projection_years: List[int],
        assumptions: Dict[str, Any],
    ):
        self.hist_pnl = historical_pnl
        self.hist_bs = historical_bs
        self.hist_cf = historical_cf
        self.hist_years = sorted(historical_years)
        self.proj_years = sorted(projection_years)
        self.assumptions = assumptions  # module → config
        self.result = ProjectionResult()

        # Working state — accumulates as each year is computed
        self.pnl: Dict[int, Dict[str, Decimal]] = {}
        self.bs: Dict[int, Dict[str, Decimal]] = {}
        self.cf: Dict[int, Dict[str, Decimal]] = {}
        self.nol_balance = ZERO  # running NOL carry-forward

        self.last_hist_year = self.hist_years[-1] if self.hist_years else None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _hist_val(self, statement: str, item: str, year: int) -> Decimal:
        data = {"PNL": self.hist_pnl, "BS": self.hist_bs, "CF": self.hist_cf}[statement]
        return d(data.get(item, {}).get(year))

    def _last_hist(self, statement: str, item: str) -> Decimal:
        if not self.last_hist_year:
            return ZERO
        return self._hist_val(statement, item, self.last_hist_year)

    def _proj_pnl(self, item: str, year: int) -> Decimal:
        return d(self.pnl.get(year, {}).get(item))

    def _proj_bs(self, item: str, year: int) -> Decimal:
        return d(self.bs.get(year, {}).get(item))

    def _prev_year(self, year: int) -> Optional[int]:
        if year in self.proj_years:
            idx = self.proj_years.index(year)
            if idx == 0:
                return self.last_hist_year
            return self.proj_years[idx - 1]
        return None

    def _get_bs(self, item: str, year: int) -> Decimal:
        """Get BS value from projected or historical."""
        if year in self.proj_years and year in self.bs:
            return d(self.bs[year].get(item))
        return self._hist_val("BS", item, year)

    def _get_pnl(self, item: str, year: int) -> Decimal:
        if year in self.proj_years and year in self.pnl:
            return d(self.pnl[year].get(item))
        return self._hist_val("PNL", item, year)

    # ------------------------------------------------------------------
    # Assumption parameter helpers
    # ------------------------------------------------------------------
    def _get_assumption(self, module: str, line_item: str) -> Optional[Dict]:
        module_data = self.assumptions.get(module, {})
        items = module_data.get("items", [])
        for item in items:
            if item.get("line_item") == line_item:
                return item
        return module_data if not items else None

    def _param(self, assumption: Dict, key: str, year: int) -> Optional[Decimal]:
        params = assumption.get("params", [])
        year_specific = None
        global_val = None
        for p in params:
            if p.get("param_key") == key:
                if p.get("year") == year:
                    year_specific = d(p["value"])
                elif p.get("year") is None:
                    global_val = d(p["value"])
        # Year-specific takes priority over global (year=None)
        if year_specific is not None:
            return year_specific
        return global_val

    def _growth_val(self, assumption: Dict, base: Decimal, year: int, year_idx: int) -> Decimal:
        method = assumption.get("projection_method", "")
        if method == "growth_flat":
            rate = self._param(assumption, "growth_rate", year) or ZERO
            return base * (1 + rate / 100)
        elif method == "growth_variable":
            rate = self._param(assumption, "growth_rate", year) or ZERO
            return base * (1 + rate / 100)
        elif method == "fixed":
            val = self._param(assumption, "value", year)
            return val if val is not None else base
        elif method == "flat":
            return base
        elif method == "pct_revenue":
            pct = self._param(assumption, "pct", year) or ZERO
            rev = self._proj_pnl("Revenue", year)
            return rev * pct / 100
        elif method == "pct_cogs":
            pct = self._param(assumption, "pct", year) or ZERO
            cogs_val = self._proj_pnl("Cost of Goods Sold", year)
            return cogs_val * pct / 100
        return base

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
                # First projection year — base from last historical
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
                # Price sub-method
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
            # Flat: carry forward last historical COGS
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
    # Step 4: PP&E roll-forward → D&A
    # ------------------------------------------------------------------
    def _compute_ppe_and_da(self, year: int, year_idx: int):
        self.pnl.setdefault(year, {})
        self.bs.setdefault(year, {})
        prev_year = self._prev_year(year)
        da_cfg = self.assumptions.get("da", {})
        capex_cfg = self.assumptions.get("capex", {})

        # Capex first (needed for PP&E gross roll-forward)
        capex = self._compute_capex_value(year, year_idx, capex_cfg)
        self.bs[year]["_capex"] = capex

        # PP&E Gross roll-forward
        ppe_gross_prev = self._get_bs("PP&E Gross", prev_year) if prev_year else ZERO
        ppe_gross = ppe_gross_prev + capex
        self.bs[year]["PP&E Gross"] = ppe_gross

        # Depreciation
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

        # Accumulated Depreciation roll-forward
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

        # Intangibles Gross — flat in MVP
        intangibles_gross_prev = self._get_bs("Intangibles Gross", prev_year) if prev_year else ZERO
        self.bs[year]["Intangibles Gross"] = intangibles_gross_prev

        # Amortization
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

        # Interest rate
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

        # Debt roll-forward
        new_debt = self._param(debt_cfg, "new_debt", year) or ZERO
        amortization = self._param(debt_cfg, "repayment", year) or ZERO

        # Existing debt amortization from schedule
        existing_repayment = self._param(debt_cfg.get("existing_debt", {}), "repayment", year) or ZERO
        total_repayment = amortization + existing_repayment

        new_total_debt = total_debt_prev + new_debt - total_repayment
        new_total_debt = max(ZERO, new_total_debt)

        self.bs[year]["Long-Term Debt"] = new_total_debt
        self.bs[year]["Short-Term Debt"] = ZERO
        self.bs[year]["_debt_issuance"] = new_debt
        self.bs[year]["_debt_repayment"] = total_repayment

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
            # Beginning-of-period cash to avoid circularity
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
        # Assuming ii, ie, other already have correct signs from historical or assumptions
        self.pnl[year]["EBT"] = ebit + ii + ie + other

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

        self.pnl[year]["Tax"] = -tax_val # Tax is an expense
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
        self.pnl[year]["Net Income"] = ebt + tax # Tax is already negative

    # ------------------------------------------------------------------
    # Step 14: Dividends
    # ------------------------------------------------------------------
    def _compute_dividends(self, year: int, year_idx: int):
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

    # ------------------------------------------------------------------
    # Step 15: Retained Earnings
    # ------------------------------------------------------------------
    def _compute_retained_earnings(self, year: int, dividends: Decimal):
        self.bs.setdefault(year, {})
        prev_year = self._prev_year(year)
        re_prev = self._get_bs("Retained Earnings", prev_year) if prev_year else ZERO
        ni = self._proj_pnl("Net Income", year)
        # Dividends are already calculated and passed in
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
    # Step 18: Cash Flow (fully derived)
    # ------------------------------------------------------------------
    def _compute_cash_flow(self, year: int):
        self.cf.setdefault(year, {})
        prev_year = self._prev_year(year)

        net_income = self._proj_pnl("Net Income", year)
        da = self._proj_pnl("D&A", year)
        amort = self._proj_pnl("Amortization of Intangibles", year)

        # ΔWorking Capital
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

        # Investing
        capex = d(self.bs[year].get("_capex", ZERO))
        d_nonop = delta("Non-Operating Assets")
        icf = -capex - d_nonop  # Increase in asset uses cash
        self.cf[year]["Capex"] = -capex
        self.cf[year]["Acquisitions / Disposals"] = -d_nonop
        self.cf[year]["Investing Cash Flow"] = icf

        # Financing
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
    def _compute_cash_bs(self, year: int, net_change: Decimal):
        self.bs.setdefault(year, {})
        prev_year = self._prev_year(year)
        cash_prev = self._get_bs("Cash & Equivalents", prev_year) if prev_year else ZERO
        cash = cash_prev + net_change
        self.bs[year]["Cash & Equivalents"] = cash
        if cash < ZERO:
            self.result.warnings.append(f"Year {year}: Negative cash balance ({cash}). Consider revising assumptions.")
        return cash

    # ------------------------------------------------------------------
    # Step 20: Non-Operating Assets, Goodwill
    # ------------------------------------------------------------------
    def _compute_nonop_assets(self, year: int):
        self.bs.setdefault(year, {})
        prev_year = self._prev_year(year)
        nonop_cfg = self.assumptions.get("non_operating", {})

        # Non-Operating Assets
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

        # Goodwill — flat in MVP
        goodwill_prev = self._get_bs("Goodwill", prev_year) if prev_year else ZERO
        self.bs[year]["Goodwill"] = goodwill_prev

        # Other Long-Term Liabilities — flat in MVP
        olt_prev = self._get_bs("Other Long-Term Liabilities", prev_year) if prev_year else ZERO
        self.bs[year]["Other Long-Term Liabilities"] = olt_prev

    # ------------------------------------------------------------------
    # Step 21: Balance Sheet validation
    # ------------------------------------------------------------------
    def _validate_balance_sheet(self, year: int):
        bs = self.bs[year]
        ppe_gross = d(bs.get("PP&E Gross", ZERO))
        acc_dep = d(bs.get("Accumulated Depreciation", ZERO))
        intangibles_gross = d(bs.get("Intangibles Gross", ZERO))
        acc_amort = d(bs.get("Accumulated Amortization", ZERO))
        goodwill = d(bs.get("Goodwill", ZERO))
        inventories = d(bs.get("Inventories", ZERO))
        ar = d(bs.get("Accounts Receivable", ZERO))
        prepaid = d(bs.get("Prepaid Expenses & Other Current Assets", ZERO))
        cash = d(bs.get("Cash & Equivalents", ZERO))
        noa = d(bs.get("Non-Operating Assets", ZERO))

        # Asset summation logic - use absolute values of all component items
        # Ensure we use Net PP&E and Net Intangibles directly
        net_ppe = d(bs.get("Net PP&E", ZERO))
        net_intang = d(bs.get("Net Intangibles", ZERO))
        goodwill = d(bs.get("Goodwill", ZERO))
        inventories = d(bs.get("Inventories", ZERO))
        ar = d(bs.get("Accounts Receivable", ZERO))
        prepaid = d(bs.get("Prepaid Expenses & Other Current Assets", ZERO))
        cash = d(bs.get("Cash & Equivalents", ZERO))
        noa = d(bs.get("Non-Operating Assets", ZERO))

        # Use max(0, v) for assets — clamped values should not inflate the total
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

        # Relative tolerance: 0.5% of total assets (or absolute floor of 1)
        tolerance = max(Decimal("1"), total_assets * Decimal("0.005"))
        if abs(residual) > tolerance:
            self.result.errors.append(
                f"Year {year}: Balance Sheet doesn't balance. "
                f"Assets={total_assets}, L+E={total_le}, Residual={residual}. "
                "Check Working Capital, Debt, and Equity assumptions."
            )
        if total_equity < ZERO:
            self.result.warnings.append(f"Year {year}: Negative equity ({total_equity}).")

        # Store totals for output
        self.bs[year]["_total_assets"] = total_assets
        self.bs[year]["_total_liabilities"] = total_liabilities
        self.bs[year]["_total_equity"] = total_equity

    # ------------------------------------------------------------------
    # Main run method
    # ------------------------------------------------------------------
    def run(self) -> ProjectionResult:
        for year_idx, year in enumerate(self.proj_years):
            # Steps 1–3
            self._compute_revenue(year, year_idx)
            self._compute_cogs(year, year_idx)
            self._compute_opex(year, year_idx)

            # Steps 4–5: PP&E + Intangibles (before EBIT)
            self._compute_ppe_and_da(year, year_idx)
            self._compute_intangibles(year, year_idx)

            # Step 6: EBIT
            self._compute_ebit(year)

            # Steps 7–9
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

            # Step 16: Equity
            self._compute_equity(year)

            # Step 17: Working Capital
            self._compute_working_capital(year, year_idx)

            # Step 18: Non-Op Assets, Goodwill, Other LT Liabilities
            self._compute_nonop_assets(year)

            # Step 19: Cash Flow
            net_change = self._compute_cash_flow(year)

            # Step 20: Cash BS
            self._compute_cash_bs(year, net_change)

            # Step 21: Validate Balance Sheet
            self._validate_balance_sheet(year)

        # Build result
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
