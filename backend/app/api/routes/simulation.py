"""Monte Carlo simulation routes — Block 4."""
import uuid
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_project_or_404
from app.api.routes.projections import _load_historical, _transform_assumptions
from app.db.base import get_db
from app.models.project import (
    AssumptionParam,
    HistoricalData,
    ProjectionAssumption,
    SimulationResult,
    ValuationInput,
)
from app.models.user import User
from app.services.monte_carlo import run_monte_carlo

router = APIRouter(prefix="/projects", tags=["simulation"])


class DriverConfig(BaseModel):
    driver: str           # "revenue_growth" | "gross_margin" | "wacc" | "terminal_growth"
    distribution: str     # "normal" | "triangular" | "uniform"
    mean: Optional[float] = None
    std: Optional[float] = None
    low: Optional[float] = None
    mode: Optional[float] = None
    high: Optional[float] = None


class MonteCarloRequest(BaseModel):
    drivers: List[DriverConfig]
    n_iterations: int = 1000
    scenario_id: Optional[str] = None
    seed: Optional[int] = None


def _load_assumptions_for_mc(project_id: str, scenario_id: Optional[str], db: Session) -> Dict:
    rows = db.query(ProjectionAssumption).filter(
        ProjectionAssumption.project_id == project_id,
        ProjectionAssumption.scenario_id.is_(None) if scenario_id is None
        else ProjectionAssumption.scenario_id == scenario_id,
    ).all()
    raw: Dict = {}
    for a in rows:
        params_db = db.query(AssumptionParam).filter(AssumptionParam.assumption_id == a.id).all()
        params = [{"param_key": p.param_key, "year": p.year, "value": Decimal(str(p.value))} for p in params_db]
        raw.setdefault(a.module, []).append({
            "line_item": a.line_item,
            "projection_method": a.projection_method,
            "params": params,
        })
    return _transform_assumptions(raw)


@router.post("/{project_id}/monte-carlo")
def run_simulation(
    project_id: str,
    body: MonteCarloRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = get_project_or_404(project_id, current_user, db)

    pnl, bs, cf, hist_years = _load_historical(project_id, db)
    if not hist_years:
        raise HTTPException(400, "No historical data uploaded")

    last_year = hist_years[-1]
    proj_years = list(range(last_year + 1, last_year + 1 + project.projection_years))

    base_assumptions = _load_assumptions_for_mc(project_id, body.scenario_id, db)

    # Load DCF inputs
    vi = db.query(ValuationInput).filter(ValuationInput.project_id == project_id).first()
    dcf_inputs = {
        "wacc": float(vi.wacc) if vi else 0.10,
        "terminal_growth_rate": float(vi.terminal_growth_rate) if vi else 0.02,
        "exit_multiple": float(vi.exit_multiple) if vi and vi.exit_multiple else None,
        "discounting_convention": vi.discounting_convention if vi else "end_of_year",
        "shares_outstanding": float(vi.shares_outstanding) if vi and vi.shares_outstanding else None,
    }

    n = min(body.n_iterations, 5000)  # cap at 5000 for safety
    driver_dicts = [d.model_dump() for d in body.drivers]

    results = run_monte_carlo(
        historical_pnl=pnl,
        historical_bs=bs,
        historical_cf=cf,
        historical_years=hist_years,
        projection_years=proj_years,
        base_assumptions=base_assumptions,
        dcf_inputs=dcf_inputs,
        driver_configs=driver_dicts,
        n_iterations=n,
        seed=body.seed,
    )

    # Persist last result
    existing = db.query(SimulationResult).filter(
        SimulationResult.project_id == project_id,
        SimulationResult.scenario_id == body.scenario_id,
    ).first()
    if existing:
        existing.results_json = results
    else:
        db.add(SimulationResult(
            id=str(uuid.uuid4()),
            project_id=project_id,
            scenario_id=body.scenario_id,
            results_json=results,
        ))
    db.commit()

    return results


@router.get("/{project_id}/monte-carlo/latest")
def get_latest_simulation(
    project_id: str,
    scenario_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_project_or_404(project_id, current_user, db)
    result = db.query(SimulationResult).filter(
        SimulationResult.project_id == project_id,
        SimulationResult.scenario_id == scenario_id,
    ).order_by(SimulationResult.ran_at.desc()).first()
    if not result:
        return {}
    return result.results_json or {}
