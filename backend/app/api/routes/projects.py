import uuid
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.base import get_db
from app.models.audit import ChangeLog
from app.models.entity import Entity
from app.models.project import Project
from app.models.user import User
from app.schemas.project import ProjectCreate, ProjectOut, ProjectUpdate
from app.services.sectors import SECTOR_BY_ID, list_sectors_grouped
from datetime import datetime
from fastapi import Query
from typing import Optional

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("/_meta/sectors")
def list_sectors():
    """Catalog of supported sectors, grouped, for the project setup picker."""
    return list_sectors_grouped()


@router.post("", response_model=ProjectOut, status_code=201)
def create_project(data: ProjectCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    base_currency = data.base_currency or data.currency
    # Validate sector against the catalog so a typo doesn't silently degrade
    # to generic defaults months later when the user wonders why the model
    # looks off. Unknown ids are rejected; an empty/None sector is allowed
    # (legacy / "I'll fill this in later").
    if data.sector and data.sector not in SECTOR_BY_ID:
        raise HTTPException(status_code=400, detail=f"Unknown sector '{data.sector}'")
    project = Project(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        name=data.name,
        currency=data.currency,
        scale=data.scale,
        fiscal_year_end=data.fiscal_year_end,
        projection_years=data.projection_years,
        project_type=data.project_type,
        base_currency=base_currency,
        sector=data.sector,
        status="draft",
    )
    db.add(project)
    db.flush()

    # Every project owns at least one entity. Single-entity projects will only
    # ever have this one; multi-entity projects can add more later. Creating
    # it up front keeps entity_id NOT NULL invariants satisfied from day one.
    db.add(Entity(
        id=str(uuid.uuid4()),
        project_id=project.id,
        name=project.name,
        entity_type="company_private",
        currency=project.currency,
        ownership_pct=100.0,
        consolidation_method="full",
        display_order=0,
    ))

    db.commit()
    db.refresh(project)
    return project


@router.get("", response_model=List[ProjectOut])
def list_projects(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Project).filter(Project.user_id == current_user.id).order_by(Project.updated_at.desc()).all()


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    project = db.query(Project).filter(Project.id == project_id, Project.user_id == current_user.id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.put("/{project_id}", response_model=ProjectOut)
def update_project(project_id: str, data: ProjectUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    project = db.query(Project).filter(Project.id == project_id, Project.user_id == current_user.id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    allowed_fields = {"name", "currency", "scale", "fiscal_year_end", "projection_years", "project_type", "base_currency", "sector"}
    payload = data.model_dump(exclude_none=True)
    if "sector" in payload and payload["sector"] and payload["sector"] not in SECTOR_BY_ID:
        raise HTTPException(status_code=400, detail=f"Unknown sector '{payload['sector']}'")
    for field, value in payload.items():
        if field not in allowed_fields:
            continue
        setattr(project, field, value)
    project.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    project = db.query(Project).filter(Project.id == project_id, Project.user_id == current_user.id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    db.delete(project)
    db.commit()


@router.get("/{project_id}/changelog")
def get_changelog(
    project_id: str,
    entity: Optional[str] = Query(default=None, description="Filter by entity type: assumption|historical|scenario|valuation"),
    since: Optional[str] = Query(default=None, description="ISO8601 datetime — only return entries after this"),
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the audit changelog for a project, newest first."""
    from app.api.deps import get_project_or_404
    get_project_or_404(project_id, current_user, db)

    q = db.query(ChangeLog, User.email).outerjoin(
        User, User.id == ChangeLog.user_id
    ).filter(ChangeLog.project_id == project_id)

    if entity:
        q = q.filter(ChangeLog.entity == entity)
    if since:
        try:
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
            q = q.filter(ChangeLog.created_at >= since_dt)
        except ValueError:
            raise HTTPException(400, f"Invalid 'since' datetime: {since}")

    rows = q.order_by(ChangeLog.created_at.desc()).limit(limit).all()

    return [
        {
            "id": entry.id,
            "user_email": email,
            "entity": entry.entity,
            "entity_id": entry.entity_id,
            "action": entry.action,
            "summary": entry.summary,
            "before_json": entry.before_json,
            "after_json": entry.after_json,
            "created_at": entry.created_at.isoformat() + "Z",
        }
        for entry, email in rows
    ]
