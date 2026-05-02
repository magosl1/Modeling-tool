"""What-If endpoint — ephemeral re-projection + DCF without persisting state.

Powers the slider panel: the user drags revenue growth +2pp, the panel POSTs
the delta map here, the backend runs the projection engine and DCF in memory
and returns the resulting equity value / EV / terminal-year EBITDA.

Persisted assumptions are *never* mutated — close the panel, the model is as
it was. To make a what-if permanent, the user creates/updates a scenario via
the existing scenario flow.
"""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_project_or_404
from app.db.base import get_db
from app.models.entity import Entity
from app.models.project import (
    AssumptionParam,
    HistoricalData,
    ProjectionAssumption,
    Scenario,
    ValuationInput,
)
from app.models.user import User
from app.services.dcf_engine import DCFEngine
from app.services.projection_engine import ProjectionEngine
from app.services.projections_runner import transform_assumptions

router = APIRouter(prefix="/projects", tags=["whatif"])


# ---------------------------------------------------------------------------
# Request schema
# ---------------------------------------------------------------------------

class WhatIfRequest(BaseModel):
    """Additive deltas (in percentage points) over the active assumptions.

    All fields are optional — clients send only the sliders the user moved.
    Numbers are pp, so revenue_growth_pp_delta=2 means "add 2pp to every
    revenue growth_rate".
    """
    scenario_id: Optional[str] = None
    revenue_growth_pp_delta: float = Field(default=0)
    cogs_growth_pp_delta: float = Field(default=0)
    opex_growth_pp_delta: float = Field(default=0)
    capex_pct_pp_delta: float = Field(default=0)
    # Absolute overrides for valuation inputs (the analyst usually wants to
    # *set* WACC and terminal growth, not nudge them — both are small numbers
    # where deltas would be confusing).
    wacc_pct: Optional[float] = None
    terminal_growth_pct: Optional[float] = None


# ---------------------------------------------------------------------------
# Helpers — assumption loading + delta application
# ---------------------------------------------------------------------------

# param_key → list of modules whose params we should bump on a given delta.
_GROWTH_PARAMS = {"growth_rate"}
_PCT_REVENUE_PARAMS = {"pct_of_revenue"}


def _load_raw_assumptions(project_id: str, scenario_id: Optional[str], db: Session) -> Dict[str, list]:
    """Fetch raw module-grouped assumptions for a scenario (None = base)."""
    q = db.query(ProjectionAssumption).filter(
        ProjectionAssumption.project_id == project_id,
    )
    if scenario_id is None:
        q = q.filter(ProjectionAssumption.scenario_id.is_(None))
    else:
        q = q.filter(ProjectionAssumption.scenario_id == scenario_id)
    rows = q.all()

    raw: Dict[str, list] = {}
    for a in rows:
        params = (
            db.query(AssumptionParam)
            .filter(AssumptionParam.assumption_id == a.id)
            .all()
        )
        raw.setdefault(a.module, []).append({
            "line_item": a.line_item,
            "projection_method": a.projection_method,
            "params": [
                {"param_key": p.param_key, "year": p.year, "value": Decimal(str(p.value))}
                for p in params
            ],
        })
    return raw


def _apply_delta_to_module(raw: Dict[str, list], module: str, delta_pp: float, target_keys: set) -> None:
    """Bump matching param values in a single module by `delta_pp` percentage points."""
    if delta_pp == 0 or module not in raw:
        return
    for item in raw[module]:
        for p in item["params"]:
            if p["param_key"] in target_keys:
                p["value"] = Decimal(str(float(p["value"]) + delta_pp))


def _load_historical(project_id: str, db: Session):
    rows = db.query(HistoricalData).filter(HistoricalData.project_id == project_id).all()
    pnl, bs, cf = {}, {}, {}
    years = set()
    for r in rows:
        target = {"PNL": pnl, "BS": bs, "CF": cf}.get(r.statement_type)
        if target is None:
            continue
        target.setdefault(r.line_item, {})[r.year] = Decimal(str(r.value))
        years.add(r.year)
    return pnl, bs, cf, sorted(years)


# ---------------------------------------------------------------------------
# Headline metrics — extracted with the same flexible matchers used elsewhere
# in the app so what-if results line up with what the user sees in the dash.
# ---------------------------------------------------------------------------

import re

_REVENUE_RX = re.compile(r"^(total\s+)?revenue|^sales|importe.*cifra", re.I)
_EBITDA_RX = re.compile(r"^ebitda$", re.I)
_EBIT_RX = re.compile(r"^ebit$|operating\s*income", re.I)
_NI_RX = re.compile(r"^net\s*income|resultado\s*neto", re.I)
_DA_RX = re.compile(r"^d&a$|depreciation\s*&\s*amortization", re.I)


def _pick(pnl: Dict, rx: re.Pattern, year: int) -> Optional[Decimal]:
    for line, vals in pnl.items():
        if rx.search(line):
            v = vals.get(year)
            if v is not None:
                return v
    return None


def _terminal_metrics(pnl: Dict[str, Dict[int, Decimal]], proj_years: List[int]) -> Dict[str, Optional[float]]:
    if not proj_years:
        return {}
    y = proj_years[-1]
    revenue = _pick(pnl, _REVENUE_RX, y)
    ebitda = _pick(pnl, _EBITDA_RX, y)
    if ebitda is None:
        # Synthesise EBITDA from EBIT + D&A when the engine doesn't emit it
        # explicitly — the engine often stops at EBIT for the IS.
        ebit, da = _pick(pnl, _EBIT_RX, y), _pick(pnl, _DA_RX, y)
        if ebit is not None and da is not None:
            ebitda = ebit + da
    return {
        "year": y,
        "revenue": float(revenue) if revenue is not None else None,
        "ebitda": float(ebitda) if ebitda is not None else None,
        "net_income": float(v) if (v := _pick(pnl, _NI_RX, y)) is not None else None,
    }


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

@router.post("/{project_id}/whatif")
def run_whatif(
    project_id: str,
    body: WhatIfRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run an in-memory what-if and return headline metrics + equity value."""
    project = get_project_or_404(project_id, current_user, db)

    # Resolve scenario id the same way the assumption routes do — base
    # scenarios collapse to NULL on the DB side.
    effective_scenario = None
    if body.scenario_id:
        s = db.query(Scenario).filter(
            Scenario.id == body.scenario_id,
            Scenario.project_id == project_id,
        ).first()
        if not s:
            raise HTTPException(404, "Scenario not found")
        effective_scenario = None if s.is_base else body.scenario_id

    raw = _load_raw_assumptions(project_id, effective_scenario, db)
    if not raw:
        raise HTTPException(400, "No assumptions configured. Build with AI or auto-seed first.")

    raw = deepcopy(raw)  # never mutate cached state
    _apply_delta_to_module(raw, "revenue", body.revenue_growth_pp_delta, _GROWTH_PARAMS)
    _apply_delta_to_module(raw, "cogs", body.cogs_growth_pp_delta, _GROWTH_PARAMS)
    _apply_delta_to_module(raw, "opex", body.opex_growth_pp_delta, _GROWTH_PARAMS)
    _apply_delta_to_module(raw, "capex", body.capex_pct_pp_delta, _PCT_REVENUE_PARAMS)

    assumptions = transform_assumptions(raw)

    pnl, bs, cf, hist_years = _load_historical(project_id, db)
    if not hist_years:
        raise HTTPException(400, "No historical data uploaded.")

    last_hist = hist_years[-1]
    proj_years = list(range(last_hist + 1, last_hist + 1 + project.projection_years))

    engine = ProjectionEngine(
        historical_pnl=pnl, historical_bs=bs, historical_cf=cf,
        historical_years=hist_years, projection_years=proj_years,
        assumptions=assumptions,
    )
    result = engine.run()
    if result.errors:
        raise HTTPException(422, detail={"error": "Projection errors", "details": result.errors})

    # Pull stored valuation inputs as the baseline; the slider only overrides
    # the two values the analyst is moving.
    saved_vi = db.query(ValuationInput).filter(ValuationInput.project_id == project_id).first()
    wacc = body.wacc_pct if body.wacc_pct is not None else (
        float(saved_vi.wacc) if saved_vi else 9.0
    )
    tg = body.terminal_growth_pct if body.terminal_growth_pct is not None else (
        float(saved_vi.terminal_growth_rate) if saved_vi else 2.0
    )
    if wacc <= tg:
        # Gordon growth blows up; report cleanly instead of returning ∞.
        return {
            "valuation_error": f"WACC ({wacc}%) must be above terminal growth ({tg}%) for Gordon-growth TV.",
            "metrics": _terminal_metrics(result.pnl, proj_years),
            "wacc": wacc,
            "terminal_growth": tg,
        }

    dcf = DCFEngine(
        pnl=result.pnl, bs=result.bs, cf=result.cf,
        projection_years=proj_years,
        wacc=Decimal(str(wacc)),
        terminal_growth_rate=Decimal(str(tg)),
        exit_multiple=Decimal(str(saved_vi.exit_multiple)) if saved_vi and saved_vi.exit_multiple else None,
        discounting_convention=saved_vi.discounting_convention if saved_vi else "end_of_year",
        shares_outstanding=Decimal(str(saved_vi.shares_outstanding)) if saved_vi and saved_vi.shares_outstanding else None,
        terminal_value_method="exit_multiple" if (saved_vi and saved_vi.exit_multiple) else "gordon_growth",
    )
    try:
        dcf_result = dcf.run()
    except ValueError as e:
        return {
            "valuation_error": str(e),
            "metrics": _terminal_metrics(result.pnl, proj_years),
            "wacc": wacc,
            "terminal_growth": tg,
        }

    return {
        "metrics": _terminal_metrics(result.pnl, proj_years),
        "valuation": {
            "enterprise_value": float(dcf_result.enterprise_value),
            "net_debt": float(dcf_result.net_debt),
            "equity_value": float(dcf_result.equity_value),
            "value_per_share": float(dcf_result.value_per_share) if dcf_result.value_per_share else None,
            "terminal_value": float(dcf_result.terminal_value),
        },
        "wacc": wacc,
        "terminal_growth": tg,
    }
