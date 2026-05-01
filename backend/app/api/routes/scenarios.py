"""Scenario management routes — create, list, delete, run, compare."""
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_project_for_write, get_project_or_404
from app.db.base import get_db
from app.models.project import (
    AssumptionParam,
    HistoricalData,
    NOLBalance,
    Project,
    ProjectedFinancial,
    ProjectionAssumption,
    Scenario,
)
from app.models.user import User
from app.services.projection_engine import ProjectionEngine
from app.services.projections_runner import load_historical, transform_assumptions

router = APIRouter(prefix="/projects", tags=["scenarios"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class ScenarioCreate(BaseModel):
    name: str
    description: Optional[str] = None
    clone_from_id: Optional[str] = None  # if set, copy all assumptions from this scenario


class ScenarioOut(BaseModel):
    id: str
    project_id: str
    name: str
    description: Optional[str]
    is_base: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_scenario_or_404(scenario_id: str, project_id: str, db: Session) -> Scenario:
    s = db.query(Scenario).filter(
        Scenario.id == scenario_id,
        Scenario.project_id == project_id
    ).first()
    if not s:
        raise HTTPException(404, "Scenario not found")
    return s


def _ensure_base_scenario(project_id: str, db: Session) -> Scenario:
    """Get or create the implicit base scenario for a project."""
    base = db.query(Scenario).filter(
        Scenario.project_id == project_id,
        Scenario.is_base == True  # noqa: E712
    ).first()
    if not base:
        base = Scenario(
            id=str(uuid.uuid4()),
            project_id=project_id,
            name="Base",
            description="Base scenario",
            is_base=True,
        )
        db.add(base)
        db.commit()
        db.refresh(base)
    return base


def _clone_assumptions(src_scenario_id: Optional[str], dst_scenario_id: str,
                       project_id: str, db: Session):
    """Copy all ProjectionAssumption + AssumptionParam rows for a scenario."""
    assumptions = db.query(ProjectionAssumption).filter(
        ProjectionAssumption.project_id == project_id,
        ProjectionAssumption.scenario_id == src_scenario_id,
    ).all()
    for a in assumptions:
        new_a = ProjectionAssumption(
            id=str(uuid.uuid4()),
            project_id=project_id,
            scenario_id=dst_scenario_id,
            module=a.module,
            line_item=a.line_item,
            projection_method=a.projection_method,
        )
        db.add(new_a)
        db.flush()
        params = db.query(AssumptionParam).filter(AssumptionParam.assumption_id == a.id).all()
        for p in params:
            db.add(AssumptionParam(
                id=str(uuid.uuid4()),
                assumption_id=new_a.id,
                param_key=p.param_key,
                year=p.year,
                value=p.value,
            ))




def _load_assumptions_for_scenario(project_id: str, scenario_id: Optional[str],
                                   db: Session) -> dict:
    """Load assumptions for a given scenario (None = base/legacy)."""
    assumptions_db = db.query(ProjectionAssumption).filter(
        ProjectionAssumption.project_id == project_id,
        ProjectionAssumption.scenario_id == scenario_id,
    ).all()
    raw: dict = {}
    for a in assumptions_db:
        params_db = db.query(AssumptionParam).filter(AssumptionParam.assumption_id == a.id).all()
        params = [{"param_key": p.param_key, "year": p.year, "value": Decimal(str(p.value))} for p in params_db]
        raw.setdefault(a.module, []).append({
            "line_item": a.line_item,
            "projection_method": a.projection_method,
            "params": params,
        })
    return transform_assumptions(raw)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/{project_id}/scenarios", response_model=List[ScenarioOut])
def list_scenarios(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_project_or_404(project_id, current_user, db)
    return db.query(Scenario).filter(Scenario.project_id == project_id).order_by(Scenario.created_at).all()


@router.post("/{project_id}/scenarios", response_model=ScenarioOut)
def create_scenario(
    project_id: str,
    body: ScenarioCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_project_for_write(project_id, current_user, db)

    # Ensure base scenario exists
    base = _ensure_base_scenario(project_id, db)

    new_scenario = Scenario(
        id=str(uuid.uuid4()),
        project_id=project_id,
        name=body.name,
        description=body.description,
        is_base=False,
    )
    db.add(new_scenario)
    db.flush()

    # Clone assumptions from source (defaults to base)
    clone_from = body.clone_from_id if body.clone_from_id else base.id
    # When cloning from "base" (is_base), source scenario_id in DB is None (legacy)
    src_is_base = db.query(Scenario).filter(Scenario.id == clone_from).first()
    src_scenario_id = None if (src_is_base and src_is_base.is_base) else clone_from
    _clone_assumptions(src_scenario_id, new_scenario.id, project_id, db)

    db.commit()
    db.refresh(new_scenario)
    return new_scenario


@router.delete("/{project_id}/scenarios/{scenario_id}")
def delete_scenario(
    project_id: str,
    scenario_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_project_for_write(project_id, current_user, db)
    scenario = _get_scenario_or_404(scenario_id, project_id, db)
    if scenario.is_base:
        raise HTTPException(400, "Cannot delete the base scenario")
    db.delete(scenario)
    db.commit()
    return {"message": "Scenario deleted"}


@router.post("/{project_id}/scenarios/{scenario_id}/run")
def run_scenario(
    project_id: str,
    scenario_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run the projection engine for a specific scenario."""
    project = get_project_for_write(project_id, current_user, db)
    scenario = _get_scenario_or_404(scenario_id, project_id, db)

    pnl, bs, cf, hist_years = load_historical(project_id, db)
    if not hist_years:
        raise HTTPException(400, "No historical data uploaded")

    # Determine which scenario_id to filter assumptions on
    effective_scenario_id = None if scenario.is_base else scenario_id
    assumptions = _load_assumptions_for_scenario(project_id, effective_scenario_id, db)

    last_hist_year = hist_years[-1]
    proj_years = list(range(last_hist_year + 1, last_hist_year + 1 + project.projection_years))

    engine = ProjectionEngine(
        historical_pnl=pnl, historical_bs=bs, historical_cf=cf,
        historical_years=hist_years, projection_years=proj_years,
        assumptions=assumptions,
    )
    result = engine.run()

    if result.errors:
        raise HTTPException(422, detail={"error": {"code": "PROJECTION_ERROR",
                                                    "message": "Projection engine errors",
                                                    "details": result.errors}})

    # Delete old projections for this scenario and store new ones
    db.query(ProjectedFinancial).filter(
        ProjectedFinancial.project_id == project_id,
        ProjectedFinancial.scenario_id == scenario_id,
    ).delete()
    db.query(NOLBalance).filter(
        NOLBalance.project_id == project_id,
        NOLBalance.scenario_id == scenario_id,
    ).delete()

    def store(data: dict, stmt_type: str):
        for line_item, year_vals in data.items():
            for year, value in year_vals.items():
                db.add(ProjectedFinancial(
                    id=str(uuid.uuid4()),
                    project_id=project_id,
                    scenario_id=scenario_id,
                    statement_type=stmt_type,
                    line_item=line_item,
                    year=year,
                    value=value,
                ))

    store(result.pnl, "PNL")
    store(result.bs, "BS")
    store(result.cf, "CF")

    for year, nol in result.nol_balances.items():
        db.add(NOLBalance(
            id=str(uuid.uuid4()),
            project_id=project_id,
            scenario_id=scenario_id,
            year=year,
            nol_opening=nol["nol_opening"],
            nol_used=nol["nol_used"],
            nol_closing=nol["nol_closing"],
        ))

    db.commit()
    return {"message": "Scenario projection complete", "scenario_id": scenario_id,
            "projection_years": proj_years, "warnings": result.warnings}


@router.get("/{project_id}/scenarios/compare")
def compare_scenarios(
    project_id: str,
    ids: str,  # comma-separated scenario IDs
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return side-by-side projection data for multiple scenarios."""
    get_project_or_404(project_id, current_user, db)
    scenario_ids = [s.strip() for s in ids.split(",") if s.strip()]
    if not scenario_ids:
        raise HTTPException(400, "Provide at least one scenario ID")

    result = {}
    for scenario_id in scenario_ids:
        scenario = db.query(Scenario).filter(
            Scenario.id == scenario_id,
            Scenario.project_id == project_id
        ).first()
        if not scenario:
            continue

        records = db.query(ProjectedFinancial).filter(
            ProjectedFinancial.project_id == project_id,
            ProjectedFinancial.scenario_id == scenario_id,
        ).all()

        data: dict = {"PNL": {}, "BS": {}, "CF": {}, "years": set()}
        for r in records:
            data[r.statement_type].setdefault(r.line_item, {})[r.year] = str(r.value)
            data["years"].add(r.year)
        data["years"] = sorted(data["years"])

        result[scenario_id] = {
            "name": scenario.name,
            "is_base": scenario.is_base,
            **data,
        }

    return result
