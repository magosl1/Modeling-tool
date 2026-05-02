import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user, get_project_for_write, get_project_or_404
from app.db.base import get_db
from app.models.project import AssumptionParam, HistoricalData, ProjectionAssumption, Scenario
from app.models.user import User

router = APIRouter(prefix="/projects", tags=["assumptions"])

MODULES = [
    "revenue", "cogs", "opex", "da", "working_capital",
    "capex", "debt", "tax", "dividends", "interest_income", "non_operating"
]


def _resolve_scenario_id(project_id: str, scenario_id: Optional[str], db: Session) -> Optional[str]:
    """Map a request-supplied scenario id to the DB convention.

    Base scenarios are stored as scenario_id=NULL on assumption rows (legacy
    convention preserved across the codebase — see scenarios.py). So if the
    caller passes the base scenario's UUID we normalise to None, otherwise we
    validate the scenario belongs to this project.
    """
    if not scenario_id:
        return None
    s = db.query(Scenario).filter(
        Scenario.id == scenario_id,
        Scenario.project_id == project_id,
    ).first()
    if not s:
        raise HTTPException(404, f"Scenario {scenario_id} not found in project")
    return None if s.is_base else scenario_id


@router.get("/{project_id}/assumptions")
def get_all_assumptions(
    project_id: str,
    scenario_id: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_project_or_404(project_id, current_user, db)
    effective_scenario = _resolve_scenario_id(project_id, scenario_id, db)
    assumptions = (
        db.query(ProjectionAssumption)
        .options(joinedload(ProjectionAssumption.params))
        .filter(
            ProjectionAssumption.project_id == project_id,
            ProjectionAssumption.scenario_id.is_(None) if effective_scenario is None
            else ProjectionAssumption.scenario_id == effective_scenario,
        )
        .all()
    )
    result = {}
    for a in assumptions:
        result.setdefault(a.module, []).append({
            "id": a.id,
            "entity_id": a.entity_id,
            "line_item": a.line_item,
            "projection_method": a.projection_method,
            "params": [{"param_key": p.param_key, "year": p.year, "value": str(p.value)} for p in a.params],
        })
    return result


@router.get("/{project_id}/assumptions/{module}")
def get_module_assumptions(
    project_id: str,
    module: str,
    scenario_id: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_project_or_404(project_id, current_user, db)
    effective_scenario = _resolve_scenario_id(project_id, scenario_id, db)
    assumptions = (
        db.query(ProjectionAssumption)
        .options(joinedload(ProjectionAssumption.params))
        .filter(
            ProjectionAssumption.project_id == project_id,
            ProjectionAssumption.module == module,
            ProjectionAssumption.scenario_id.is_(None) if effective_scenario is None
            else ProjectionAssumption.scenario_id == effective_scenario,
        )
        .all()
    )
    return [
        {
            "id": a.id,
            "entity_id": a.entity_id,
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
    scenario_id: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Save/overwrite assumption configuration for a module within a scenario.

    When scenario_id is omitted (or refers to the base scenario) we operate on
    the legacy NULL bucket so existing single-scenario projects keep working.
    """
    if module not in MODULES:
        raise HTTPException(400, f"Unknown module: {module}")
    get_project_for_write(project_id, current_user, db)
    effective_scenario = _resolve_scenario_id(project_id, scenario_id, db)

    # Delete existing assumptions for this module *within the target scenario only*.
    # Without the scenario filter, editing an Upside scenario would silently wipe
    # the Base scenario's data — exactly the bug the override UI exists to fix.
    existing_q = db.query(ProjectionAssumption).filter(
        ProjectionAssumption.project_id == project_id,
        ProjectionAssumption.module == module,
    )
    if effective_scenario is None:
        existing_q = existing_q.filter(ProjectionAssumption.scenario_id.is_(None))
    else:
        existing_q = existing_q.filter(ProjectionAssumption.scenario_id == effective_scenario)
    for a in existing_q.all():
        db.delete(a)  # cascade deletes params via ORM relationship
    db.flush()

    # Get the entity_id to use
    # In multi-entity projects, it should come from the item or a param
    # For backward compatibility, if not provided, use the project's first entity
    from app.models.project import Entity
    default_entity = db.query(Entity).filter(Entity.project_id == project_id).first()
    if not default_entity:
        raise HTTPException(400, "Project has no entities. Please create one first.")

    # Insert new
    for item in data:
        item_entity_id = item.get("entity_id") or default_entity.id
        
        assumption = ProjectionAssumption(
            id=str(uuid.uuid4()),
            project_id=project_id,
            entity_id=item_entity_id,
            scenario_id=effective_scenario,
            module=module,
            line_item=item.get("line_item", ""),
            projection_method=item.get("projection_method", ""),
        )
        db.add(assumption)
        db.flush()

        for param in item.get("params", []):
            param_value = param.get("value")
            if param_value == "" or param_value is None:
                param_value = None
            else:
                param_value = str(param_value)
                
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
    scenario_id: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns status per module: not_started | configured | complete | error."""
    get_project_or_404(project_id, current_user, db)
    effective_scenario = _resolve_scenario_id(project_id, scenario_id, db)
    has_historical = db.query(HistoricalData.id).filter(HistoricalData.project_id == project_id).first() is not None

    # Single query with eager loading instead of N+1
    assumptions_q = (
        db.query(ProjectionAssumption)
        .options(joinedload(ProjectionAssumption.params))
        .filter(ProjectionAssumption.project_id == project_id)
    )
    if effective_scenario is None:
        assumptions_q = assumptions_q.filter(ProjectionAssumption.scenario_id.is_(None))
    else:
        assumptions_q = assumptions_q.filter(ProjectionAssumption.scenario_id == effective_scenario)
    assumptions = assumptions_q.all()

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
            # An assumption is considered "configured" if it has a projection method.
            # It's "complete" if it's configured and historical data exists.
            all_configured = all(
                a.projection_method and a.projection_method.strip() != ""
                for a in module_assumptions
            )
            if all_configured and has_historical:
                status = "complete"
            else:
                status = "configured"
        statuses.append({"module": module, "status": status})

    return statuses

@router.post("/{project_id}/assumptions/auto-seed")
def auto_seed_assumptions(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_project_for_write(project_id, current_user, db)
    from app.services.assumption_service import seed_default_assumptions
    seed_default_assumptions(project_id, db)
    return {"message": "Default assumptions seeded based on historical data"}
