"""Entity CRUD routes — Phase 0 of the universal modeling platform."""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.db.base import get_db
from app.models.user import User
from app.models.project import Project, HistoricalData, ProjectionAssumption, ProjectedFinancial
from app.models.entity import Entity
from app.api.deps import get_current_user, get_project_or_404
from app.schemas.entity import EntityCreate, EntityUpdate, EntityOut, BulkCreateRequest, CloneEntityRequest

router = APIRouter(tags=["entities"])


def get_entity_or_404(entity_id: str, user: User, db: Session) -> Entity:
    """Fetch an entity and verify the caller owns its project."""
    entity = (
        db.query(Entity)
        .join(Project, Project.id == Entity.project_id)
        .filter(Entity.id == entity_id, Project.user_id == user.id)
        .first()
    )
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity


def get_or_create_default_entity(project: Project, db: Session) -> Entity:
    """
    For single_entity projects: ensure at least one entity exists.
    Returns the first/only entity, creating one if the project has none.
    """
    if project.entities:
        return project.entities[0]

    entity = Entity(
        id=str(uuid.uuid4()),
        project_id=project.id,
        name=project.name,
        entity_type="company_private",
        currency=project.currency,
        ownership_pct=100.0,
        consolidation_method="full",
        display_order=0,
    )
    db.add(entity)
    db.flush()  # get the id without committing

    # Backfill entity_id on all existing records for this project
    db.query(HistoricalData).filter(
        HistoricalData.project_id == project.id,
        HistoricalData.entity_id == None,  # noqa: E711
    ).update({"entity_id": entity.id})
    db.query(ProjectionAssumption).filter(
        ProjectionAssumption.project_id == project.id,
        ProjectionAssumption.entity_id == None,  # noqa: E711
    ).update({"entity_id": entity.id})
    db.query(ProjectedFinancial).filter(
        ProjectedFinancial.project_id == project.id,
        ProjectedFinancial.entity_id == None,  # noqa: E711
    ).update({"entity_id": entity.id})

    db.commit()
    db.refresh(entity)
    return entity


# ---------------------------------------------------------------------------
# List entities for a project
# ---------------------------------------------------------------------------

@router.get("/projects/{project_id}/entities", response_model=List[EntityOut])
def list_entities(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = get_project_or_404(project_id, current_user, db)
    # Auto-provision a default entity for single_entity projects that have none
    if project.project_type == "single_entity" and not project.entities:
        get_or_create_default_entity(project, db)
        db.refresh(project)
    return project.entities


# ---------------------------------------------------------------------------
# Create entity
# ---------------------------------------------------------------------------

@router.post("/projects/{project_id}/entities", response_model=EntityOut, status_code=201)
def create_entity(
    project_id: str,
    payload: EntityCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = get_project_or_404(project_id, current_user, db)

    if payload.parent_entity_id:
        parent = db.query(Entity).filter(
            Entity.id == payload.parent_entity_id,
            Entity.project_id == project_id,
        ).first()
        if not parent:
            raise HTTPException(400, "parent_entity_id not found in this project")

    entity = Entity(
        id=str(uuid.uuid4()),
        project_id=project_id,
        **payload.model_dump(),
    )
    db.add(entity)

    # If this is the first entity and it's a single_entity project, upgrade to multi_entity
    if project.project_type == "single_entity" and not project.entities:
        project.project_type = "multi_entity"

    db.commit()
    db.refresh(entity)
    return entity


# ---------------------------------------------------------------------------
# Get single entity
# ---------------------------------------------------------------------------

@router.get("/entities/{entity_id}", response_model=EntityOut)
def get_entity(
    entity_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_entity_or_404(entity_id, current_user, db)


# ---------------------------------------------------------------------------
# Update entity
# ---------------------------------------------------------------------------

@router.put("/entities/{entity_id}", response_model=EntityOut)
def update_entity(
    entity_id: str,
    payload: EntityUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    entity = get_entity_or_404(entity_id, current_user, db)

    if payload.parent_entity_id is not None:
        if payload.parent_entity_id == entity_id:
            raise HTTPException(400, "An entity cannot be its own parent")
        parent = db.query(Entity).filter(
            Entity.id == payload.parent_entity_id,
            Entity.project_id == entity.project_id,
        ).first()
        if not parent:
            raise HTTPException(400, "parent_entity_id not found in this project")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(entity, field, value)

    entity.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(entity)
    return entity


# ---------------------------------------------------------------------------
# Delete entity
# ---------------------------------------------------------------------------

@router.delete("/entities/{entity_id}", status_code=204)
def delete_entity(
    entity_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    entity = get_entity_or_404(entity_id, current_user, db)

    # Prevent deleting the last entity in a project
    project = db.query(Project).filter(Project.id == entity.project_id).first()
    if project and len(project.entities) <= 1:
        raise HTTPException(
            400,
            "Cannot delete the only entity in a project. Delete the project instead.",
        )

    db.delete(entity)
    db.commit()


# ---------------------------------------------------------------------------
# Clone entity (deep copy: historical data + assumptions)
# ---------------------------------------------------------------------------

@router.post("/entities/{entity_id}/clone", response_model=EntityOut, status_code=201)
def clone_entity(
    entity_id: str,
    payload: CloneEntityRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    source = get_entity_or_404(entity_id, current_user, db)

    new_entity = Entity(
        id=str(uuid.uuid4()),
        project_id=source.project_id,
        parent_entity_id=source.parent_entity_id,
        name=payload.new_name,
        entity_type=source.entity_type,
        ticker=None,
        exchange=None,
        currency=source.currency,
        country=source.country,
        sector=source.sector,
        description=source.description,
        ownership_pct=(payload.overrides or {}).get("ownership_pct", source.ownership_pct),
        consolidation_method=(payload.overrides or {}).get("consolidation_method", source.consolidation_method),
        is_active=True,
        start_date=source.start_date,
        end_date=source.end_date,
        display_order=source.display_order + 1,
    )
    db.add(new_entity)
    db.flush()

    # Clone historical data
    hist_records = db.query(HistoricalData).filter(
        HistoricalData.entity_id == source.id
    ).all()
    for r in hist_records:
        db.add(HistoricalData(
            id=str(uuid.uuid4()),
            project_id=r.project_id,
            entity_id=new_entity.id,
            statement_type=r.statement_type,
            line_item=r.line_item,
            bucket=r.bucket,
            year=r.year,
            value=r.value,
        ))

    # Clone assumptions
    assumption_records = db.query(ProjectionAssumption).filter(
        ProjectionAssumption.entity_id == source.id,
        ProjectionAssumption.scenario_id == None,  # noqa: E711
    ).all()
    for a in assumption_records:
        from app.models.project import AssumptionParam
        new_assumption = ProjectionAssumption(
            id=str(uuid.uuid4()),
            project_id=a.project_id,
            entity_id=new_entity.id,
            scenario_id=None,
            module=a.module,
            line_item=a.line_item,
            projection_method=a.projection_method,
        )
        db.add(new_assumption)
        db.flush()
        for p in a.params:
            db.add(AssumptionParam(
                id=str(uuid.uuid4()),
                assumption_id=new_assumption.id,
                param_key=p.param_key,
                year=p.year,
                value=p.value,
            ))

    db.commit()
    db.refresh(new_entity)
    return new_entity


# ---------------------------------------------------------------------------
# Bulk create entities from a template
# ---------------------------------------------------------------------------

@router.post("/projects/{project_id}/entities/bulk-create", response_model=List[EntityOut], status_code=201)
def bulk_create_entities(
    project_id: str,
    payload: BulkCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = get_project_or_404(project_id, current_user, db)
    created = []

    for i in range(1, payload.count + 1):
        name = payload.naming_pattern.replace("{name}", payload.template.name).replace("{n}", str(i))
        data = payload.template.model_dump()
        data["name"] = name
        data["display_order"] = i - 1

        entity = Entity(id=str(uuid.uuid4()), project_id=project_id, **data)
        db.add(entity)
        created.append(entity)

    if project.project_type == "single_entity" and payload.count > 0:
        project.project_type = "multi_entity"

    db.commit()
    for e in created:
        db.refresh(e)
    return created


# ---------------------------------------------------------------------------
# Entity-level historical data routes (proxies that use entity_id)
# ---------------------------------------------------------------------------

@router.get("/entities/{entity_id}/historical")
def get_entity_historical(
    entity_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    entity = get_entity_or_404(entity_id, current_user, db)
    records = db.query(HistoricalData).filter(
        HistoricalData.entity_id == entity.id
    ).all()

    result: dict = {"PNL": {}, "BS": {}, "CF": {}}
    for r in records:
        result[r.statement_type].setdefault(r.line_item, {})[r.year] = str(r.value)
    return result


@router.get("/entities/{entity_id}/projections")
def get_entity_projections(
    entity_id: str,
    scenario_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    entity = get_entity_or_404(entity_id, current_user, db)
    q = db.query(ProjectedFinancial).filter(
        ProjectedFinancial.entity_id == entity.id
    )
    if scenario_id:
        q = q.filter(ProjectedFinancial.scenario_id == scenario_id)
    else:
        q = q.filter(ProjectedFinancial.scenario_id == None)  # noqa: E711

    records = q.all()
    result: dict = {"PNL": {}, "BS": {}, "CF": {}}
    for r in records:
        result[r.statement_type].setdefault(r.line_item, {})[r.year] = str(r.value)
    return result
