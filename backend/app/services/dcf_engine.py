"""
DCF Valuation Engine.

FCFF = EBIT × (1 − Tax Rate) + D&A + Amortization − ΔWC − Capex
Terminal Value: Gordon Growth Model or Exit Multiple
Sensitivity: 5×5 matrix WACC × Terminal Growth Rate
"""
from decimal import Decimal
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from app.services.utils import ZERO, d


@dataclass
class DCFResult:
    fcff_by_year: Dict[int, Decimal] = field(default_factory=dict)
    fcff_build_up: Dict[int, Dict[str, Decimal]] = field(default_factory=dict)
    normalized_terminal_year: Optional[int] = None
    terminal_fcff_build_up: Dict[str, Decimal] = field(default_factory=dict)
    implied_multiples: Dict[int, Dict[str, Optional[Decimal]]] = field(default_factory=dict)
    enterprise_value: Decimal = ZERO
    net_debt: Decimal = ZERO
    equity_value: Decimal = ZERO
    value_per_share: Optional[Decimal] = None
    terminal_value: Decimal = ZERO
    pv_fcffs: Decimal = ZERO
    pv_terminal_value: Decimal = ZERO
    method_used: str = "gordon_growth"
    sensitivity_table: Dict[str, Dict[str, Decimal]] = field(default_factory=dict)


class DCFEngine:
    def __init__(
        self,
        pnl: Dict[str, Dict[int, Decimal]],  # projected P&L
        bs: Dict[str, Dict[int, Decimal]],    # projected BS
        cf: Dict[str, Dict[int, Decimal]],    # projected CF
        projection_years: List[int],
        wacc: Decimal,
        terminal_growth_rate: Decimal,
        exit_multiple: Optional[Decimal],
        discounting_convention: str,  # "end_of_year" | "mid_year"
        shares_outstanding: Optional[Decimal],
        terminal_value_method: str = "gordon_growth",  # "gordon_growth" | "exit_multiple"
    ):
        self.pnl = pnl
        self.bs = bs
        self.cf = cf
        self.years = sorted(projection_years)
        self.wacc = wacc
        self.terminal_growth_rate = terminal_growth_rate
        self.exit_multiple = exit_multiple
        self.discounting_convention = discounting_convention
        self.shares_outstanding = shares_outstanding
        self.tv_method = terminal_value_method
        self.fcff_by_year: Dict[int, Decimal] = {}
        self.net_debt: Decimal = ZERO

    def _get_pnl(self, item: str, year: int) -> Decimal:
        return d(self.pnl.get(item, {}).get(year))

    def _get_bs(self, item: str, year: int) -> Decimal:
        return d(self.bs.get(item, {}).get(year))

    def _get_cf(self, item: str, year: int) -> Decimal:
        return d(self.cf.get(item, {}).get(year))

    def _compute_fcff(self, year: int) -> Dict[str, Decimal]:
        """FCFF = EBIT × (1 − Tax Rate) + D&A + Amortization − ΔWC − Capex"""
        ebit = self._get_pnl("EBIT", year)
        tax = self._get_pnl("Tax", year)
        ebt = self._get_pnl("EBT", year)

        # Effective tax rate from projections.
        # Tax is stored as a negative value (expense) in the projection P&L,
        # so we use abs(tax) to derive a positive rate in [0, 1].
        tax_rate = (abs(tax) / ebt) if ebt > ZERO else ZERO
        tax_rate = max(ZERO, min(Decimal("1"), tax_rate))

        taxes_nopat = ebit * tax_rate
        nopat = ebit - taxes_nopat
        da = self._get_pnl("D&A", year)
        amort = self._get_pnl("Amortization of Intangibles", year)
        delta_wc = -self._get_cf("Changes in Working Capital", year)  # CF shows as subtracted already
        capex = abs(self._get_cf("Capex", year))  # Capex is negative in CF statement

        fcff = nopat + da + amort - delta_wc - capex
        
        return {
            "EBIT": ebit,
            "Taxes": -taxes_nopat,
            "NOPAT": nopat,
            "D&A & Amort": da + amort,
            "Less: Changes in WC": -delta_wc,
            "Less: Capex": -capex,
            "FCFF": fcff
        }

    def _discount_factor(self, year_idx: int) -> Decimal:
        """Compute discount factor. year_idx is 1-based (1 = first projection year)."""
        if self.discounting_convention == "mid_year":
            t = Decimal(str(year_idx)) - Decimal("0.5")
        else:
            t = Decimal(str(year_idx))
        return (1 + self.wacc / 100) ** t

    def _compute_terminal_value(self, last_fcff: Decimal, last_year: int) -> Decimal:
        if self.tv_method == "exit_multiple" and self.exit_multiple is not None:
            ebitda = (
                self._get_pnl("EBIT", last_year)
                + self._get_pnl("D&A", last_year)
                + self._get_pnl("Amortization of Intangibles", last_year)
            )
            return ebitda * self.exit_multiple
        else:
            # Gordon Growth Model
            g = self.terminal_growth_rate / 100
            wacc_rate = self.wacc / 100
            if wacc_rate <= g:
                raise ValueError(f"WACC ({wacc_rate}) must be greater than terminal growth rate ({g})")
            return last_fcff * (1 + g) / (wacc_rate - g)

    def _build_sensitivity(self, base_wacc: Decimal, base_g: Decimal) -> Dict[str, Dict[str, Decimal]]:
        """Build 5×5 sensitivity table: WACC ±1% in 0.5% steps × Terminal Growth ±1% in 0.5% steps."""
        wacc_steps = [base_wacc + Decimal(str(i * 0.5 - 1)) for i in range(5)]
        g_steps = [base_g + Decimal(str(i * 0.5 - 1)) for i in range(5)]

        table = {}
        for w in wacc_steps:
            w_key = str(w)
            table[w_key] = {}
            for g in g_steps:
                g_key = str(g)
                try:
                    pv_fcffs = ZERO
                    for idx, year in enumerate(self.years, 1):
                        fcff = d(self.fcff_by_year.get(year, ZERO))
                        if self.discounting_convention == "mid_year":
                            t = Decimal(str(idx)) - Decimal("0.5")
                        else:
                            t = Decimal(str(idx))
                        pv_fcffs += fcff / (1 + w / 100) ** t

                    last_fcff = d(self.fcff_by_year.get(self.years[-1], ZERO))
                    if self.tv_method == "exit_multiple" and self.exit_multiple is not None:
                        last_year = self.years[-1]
                        ebitda = (
                            self._get_pnl("EBIT", last_year)
                            + self._get_pnl("D&A", last_year)
                            + self._get_pnl("Amortization of Intangibles", last_year)
                        )
                        tv = ebitda * self.exit_multiple
                    else:
                        g_rate = g / 100
                        w_rate = w / 100
                        if w_rate <= g_rate:
                            tv = ZERO
                        else:
                            tv = last_fcff * (1 + g_rate) / (w_rate - g_rate)

                    n = len(self.years)
                    if self.discounting_convention == "mid_year":
                        t = Decimal(str(n)) - Decimal("0.5")
                    else:
                        t = Decimal(str(n))
                    pv_tv = tv / (1 + w / 100) ** t
                    ev = pv_fcffs + pv_tv
                    eq = ev - self.net_debt
                    vps = eq / self.shares_outstanding if self.shares_outstanding else None
                    table[w_key][g_key] = vps if vps is not None else eq
                except Exception:
                    table[w_key][g_key] = ZERO
        return table

    def run(self) -> DCFResult:
        result = DCFResult(method_used=self.tv_method)
        self.fcff_by_year = {}
        result.fcff_build_up = {}

        # Compute FCFF per year
        for year in self.years:
            build_up = self._compute_fcff(year)
            fcff = build_up["FCFF"]
            self.fcff_by_year[year] = fcff
            result.fcff_build_up[year] = build_up

        result.fcff_by_year = {y: v for y, v in self.fcff_by_year.items()}

        # PV of FCFFs
        pv_fcffs = ZERO
        for idx, year in enumerate(self.years, 1):
            fcff = self.fcff_by_year[year]
            df = self._discount_factor(idx)
            pv_fcffs += fcff / df
        result.pv_fcffs = pv_fcffs

        # Terminal Value
        last_year = self.years[-1]
        last_fcff = self.fcff_by_year[last_year]
        tv = self._compute_terminal_value(last_fcff, last_year)
        result.terminal_value = tv

        # PV of Terminal Value
        n = len(self.years)
        df_last = self._discount_factor(n)
        pv_tv = tv / df_last
        result.pv_terminal_value = pv_tv

        # Enterprise Value
        result.enterprise_value = pv_fcffs + pv_tv

        # Net Debt
        st_debt = self._get_bs("Short-Term Debt", last_year)
        lt_debt = self._get_bs("Long-Term Debt", last_year)
        cash = self._get_bs("Cash & Equivalents", last_year)
        net_debt = st_debt + lt_debt - cash
        result.net_debt = net_debt
        self.net_debt = net_debt

        # Equity Value
        result.equity_value = result.enterprise_value - net_debt

        # Value per Share
        if self.shares_outstanding is not None and self.shares_outstanding > 0:
            result.value_per_share = result.equity_value / self.shares_outstanding

        # Terminal Year Build-up (Normalized + 1)
        result.normalized_terminal_year = last_year + 1
        g_rate = self.terminal_growth_rate / 100
        result.terminal_fcff_build_up = {
            k: v * (1 + g_rate) for k, v in result.fcff_build_up[last_year].items()
        }

        # Implied Multiples
        for year in self.years:
            ebitda = (
                self._get_pnl("EBIT", year)
                + self._get_pnl("D&A", year)
                + self._get_pnl("Amortization of Intangibles", year)
            )
            revenue = self._get_pnl("Revenue", year)
            net_income = self._get_pnl("Net Income", year)
            
            multiples: Dict[str, Optional[Decimal]] = {}
            if ebitda > 0:
                multiples["EV / EBITDA"] = result.enterprise_value / ebitda
            if revenue > 0:
                multiples["EV / Revenue"] = result.enterprise_value / revenue
            if net_income > 0 and result.equity_value > 0:
                multiples["P / E"] = result.equity_value / net_income
                
            result.implied_multiples[year] = multiples

        # Sensitivity Table
        result.sensitivity_table = self._build_sensitivity(self.wacc, self.terminal_growth_rate)

        return result
