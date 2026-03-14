from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict
from app.db.base import get_db
from app.models.user import User
from app.models.project import Project, ProjectionAssumption, AssumptionParam, HistoricalData
from app.api.deps import get_current_user, get_project_or_404
import uuid
from datetime import datetime, timezone

router = APIRouter(prefix="/projects", tags=["assumptions"])

MODULES = [
    "revenue", "cogs", "opex", "da", "working_capital",
    "capex", "debt", "tax", "dividends", "interest_income", "non_operating"
]


@router.get("/{project_id}/assumptions")
def get_all_assumptions(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_project_or_404(project_id, current_user, db)
    assumptions = db.query(ProjectionAssumption).filter(ProjectionAssumption.project_id == project_id).all()
    result = {}
    for a in assumptions:
        params = db.query(AssumptionParam).filter(AssumptionParam.assumption_id == a.id).all()
        result.setdefault(a.module, []).append({
            "id": a.id,
            "line_item": a.line_item,
            "projection_method": a.projection_method,
            "params": [{"param_key": p.param_key, "year": p.year, "value": str(p.value)} for p in params],
        })
    return result


@router.get("/{project_id}/assumptions/{module}")
def get_module_assumptions(
    project_id: str,
    module: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_project_or_404(project_id, current_user, db)
    assumptions = db.query(ProjectionAssumption).filter(
        ProjectionAssumption.project_id == project_id,
        ProjectionAssumption.module == module,
    ).all()
    result = []
    for a in assumptions:
        params = db.query(AssumptionParam).filter(AssumptionParam.assumption_id == a.id).all()
        result.append({
            "id": a.id,
            "line_item": a.line_item,
            "projection_method": a.projection_method,
            "params": [{"param_key": p.param_key, "year": p.year, "value": str(p.value)} for p in params],
        })
    return result


@router.put("/{project_id}/assumptions/{module}")
def save_module_assumptions(
    project_id: str,
    module: str,
    data: List[Dict],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Save/overwrite assumption configuration for a module."""
    if module not in MODULES:
        raise HTTPException(400, f"Unknown module: {module}")
    get_project_or_404(project_id, current_user, db)

    # Delete existing assumptions for this module
    existing = db.query(ProjectionAssumption).filter(
        ProjectionAssumption.project_id == project_id,
        ProjectionAssumption.module == module,
    ).all()
    for a in existing:
        db.query(AssumptionParam).filter(AssumptionParam.assumption_id == a.id).delete()
        db.delete(a)

    # Insert new
    for item in data:
        assumption = ProjectionAssumption(
            id=str(uuid.uuid4()),
            project_id=project_id,
            module=module,
            line_item=item.get("line_item", ""),
            projection_method=item.get("projection_method", ""),
        )
        db.add(assumption)
        db.flush()

        for param in item.get("params", []):
            db.add(AssumptionParam(
                id=str(uuid.uuid4()),
                assumption_id=assumption.id,
                param_key=param["param_key"],
                year=param.get("year"),
                value=param["value"],
            ))

    db.commit()
    return {"message": f"Module '{module}' assumptions saved"}


@router.get("/{project_id}/modules/status")
def get_module_status(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns status per module: not_started | configured | complete | error."""
    get_project_or_404(project_id, current_user, db)
    has_historical = db.query(HistoricalData).filter(HistoricalData.project_id == project_id).first() is not None

    statuses = []
    for module in MODULES:
        assumptions = db.query(ProjectionAssumption).filter(
            ProjectionAssumption.project_id == project_id,
            ProjectionAssumption.module == module,
        ).all()

        if not assumptions:
            status = "not_started"
        else:
            # Check if all assumptions have params
            all_have_params = all(
                db.query(AssumptionParam).filter(AssumptionParam.assumption_id == a.id).first() is not None
                for a in assumptions
            )
            if all_have_params and has_historical:
                status = "complete"
            else:
                status = "configured"

        statuses.append({"module": module, "status": status})

    return statuses
