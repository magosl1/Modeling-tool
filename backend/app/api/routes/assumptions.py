from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import List, Dict
from app.db.base import get_db
from app.models.user import User
from app.models.project import ProjectionAssumption, AssumptionParam, HistoricalData
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
    assumptions = (
        db.query(ProjectionAssumption)
        .options(joinedload(ProjectionAssumption.params))
        .filter(ProjectionAssumption.project_id == project_id)
        .all()
    )
    result = {}
    for a in assumptions:
        result.setdefault(a.module, []).append({
            "id": a.id,
            "line_item": a.line_item,
            "projection_method": a.projection_method,
            "params": [{"param_key": p.param_key, "year": p.year, "value": str(p.value)} for p in a.params],
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
    assumptions = (
        db.query(ProjectionAssumption)
        .options(joinedload(ProjectionAssumption.params))
        .filter(
            ProjectionAssumption.project_id == project_id,
            ProjectionAssumption.module == module,
        )
        .all()
    )
    return [
        {
            "id": a.id,
            "line_item": a.line_item,
            "projection_method": a.projection_method,
            "params": [{"param_key": p.param_key, "year": p.year, "value": str(p.value)} for p in a.params],
        }
        for a in assumptions
    ]


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
        db.delete(a)  # cascade deletes params via ORM relationship
    db.flush()

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
            param_value = param.get("value", "0")
            if param_value == "" or param_value is None:
                param_value = "0"
            db.add(AssumptionParam(
                id=str(uuid.uuid4()),
                assumption_id=assumption.id,
                param_key=param["param_key"],
                year=param.get("year"),
                value=param_value,
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
    has_historical = db.query(HistoricalData.id).filter(HistoricalData.project_id == project_id).first() is not None

    # Single query with eager loading instead of N+1
    assumptions = (
        db.query(ProjectionAssumption)
        .options(joinedload(ProjectionAssumption.params))
        .filter(ProjectionAssumption.project_id == project_id)
        .all()
    )

    # Group by module
    by_module: Dict[str, list] = {}
    for a in assumptions:
        by_module.setdefault(a.module, []).append(a)

    statuses = []
    for module in MODULES:
        module_assumptions = by_module.get(module, [])
        if not module_assumptions:
            status = "not_started"
        else:
            all_have_params = all(len(a.params) > 0 for a in module_assumptions)
            if all_have_params and has_historical:
                status = "complete"
            else:
                status = "configured"
        statuses.append({"module": module, "status": status})

    return statuses
