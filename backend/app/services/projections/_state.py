"""State, constructor, and low-level helpers shared by every mixin.

The ProjectionEngine in `engine.py` composes this base with the three
domain mixins (income_statement, balance_sheet, cash_flow). The split
is mechanical — method bodies are unchanged, only their home file moves.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, List, Optional

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


class _EngineState:
    """Constructor + shared lookup helpers. Sets up `self.pnl/bs/cf/result`
    and the historical/projection year metadata consumed by every step.
    """

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
        self.assumptions = assumptions
        self.result = ProjectionResult()

        self.pnl: Dict[int, Dict[str, Decimal]] = {}
        self.bs: Dict[int, Dict[str, Decimal]] = {}
        self.cf: Dict[int, Dict[str, Decimal]] = {}
        self.nol_balance = ZERO

        self.last_hist_year = self.hist_years[-1] if self.hist_years else None

        self._prev_year_map: Dict[int, Optional[int]] = {}
        for i, y in enumerate(self.proj_years):
            self._prev_year_map[y] = self.last_hist_year if i == 0 else self.proj_years[i - 1]

    # -- Historical / projection lookups --------------------------------
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
        return self._prev_year_map.get(year)

    def _get_bs(self, item: str, year: int) -> Decimal:
        if year in self.proj_years and year in self.bs:
            return d(self.bs[year].get(item))
        return self._hist_val("BS", item, year)

    def _get_pnl(self, item: str, year: int) -> Decimal:
        if year in self.proj_years and year in self.pnl:
            return d(self.pnl[year].get(item))
        return self._hist_val("PNL", item, year)

    # -- Assumption parameter helpers -----------------------------------
    def _get_assumption(self, module: str, line_item: str) -> Optional[Dict]:
        module_data = self.assumptions.get(module, {})
        items = module_data.get("items", [])
        for item in items:
            if item.get("line_item") == line_item:
                return item
        return module_data if not items else None

    @staticmethod
    def _build_param_index(assumption: Dict) -> Dict:
        """Build a {(param_key, year): value} index for O(1) lookup."""
        index: Dict = {}
        for p in assumption.get("params", []):
            index[(p["param_key"], p.get("year"))] = d(p["value"])
        return index

    def _param(self, assumption: Dict, key: str, year: int) -> Optional[Decimal]:
        index = assumption.get("_param_index")
        if index is None:
            index = self._build_param_index(assumption)
            assumption["_param_index"] = index
        year_val = index.get((key, year))
        if year_val is not None:
            return year_val
        return index.get((key, None))

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
