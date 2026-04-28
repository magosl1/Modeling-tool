"""Admin routes — usage stats and user management.

Access:
- GET /admin/stats          — admin or master_admin
- GET /admin/users          — admin or master_admin
- PATCH /admin/users/{id}   — master_admin only (role + soft-delete mutations)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import require_admin, require_master_admin
from app.db.base import get_db
from app.models.entity import Entity
from app.models.project import HistoricalData, Project, UploadedFile
from app.models.user import User

router = APIRouter(prefix="/admin", tags=["admin"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class StatsResponse(BaseModel):
    users_total: int
    users_active: int           # not soft-deleted
    users_new_30d: int
    users_admins: int
    users_master_admins: int

    projects_total: int
    projects_by_status: dict[str, int]
    projects_new_30d: int

    entities_total: int
    entities_by_type: dict[str, int]

    historical_rows: int
    uploads_total: int
    uploads_validated: int
    uploads_rejected: int
    uploads_pending: int

    timestamp: datetime


class AdminUserOut(BaseModel):
    id: str
    email: str
    name: str
    role: str
    auth_provider: str
    created_at: datetime
    deleted_at: Optional[datetime] = None
    project_count: int

    model_config = {"from_attributes": True}


class AdminUserListResponse(BaseModel):
    items: list[AdminUserOut]
    total: int
    page: int
    page_size: int


class UpdateUserRequest(BaseModel):
    role: Optional[Literal["user", "admin", "master_admin"]] = None
    deactivate: Optional[bool] = None  # True -> set deleted_at; False -> clear


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

@router.get("/stats", response_model=StatsResponse)
def get_stats(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> StatsResponse:
    """Aggregate usage metrics for the platform."""
    cutoff_30d = datetime.now(timezone.utc) - timedelta(days=30)

    # Users
    users_total = db.query(func.count(User.id)).scalar() or 0
    users_active = (
        db.query(func.count(User.id)).filter(User.deleted_at.is_(None)).scalar() or 0
    )
    users_new_30d = (
        db.query(func.count(User.id)).filter(User.created_at >= cutoff_30d).scalar() or 0
    )
    role_counts = dict(
        db.query(User.role, func.count(User.id)).group_by(User.role).all()
    )

    # Projects
    projects_total = db.query(func.count(Project.id)).scalar() or 0
    projects_by_status = dict(
        db.query(Project.status, func.count(Project.id))
        .group_by(Project.status)
        .all()
    )
    projects_new_30d = (
        db.query(func.count(Project.id))
        .filter(Project.created_at >= cutoff_30d)
        .scalar()
        or 0
    )

    # Entities
    entities_total = db.query(func.count(Entity.id)).scalar() or 0
    entities_by_type = dict(
        db.query(Entity.entity_type, func.count(Entity.id))
        .group_by(Entity.entity_type)
        .all()
    )

    # Data volume
    historical_rows = db.query(func.count(HistoricalData.id)).scalar() or 0

    uploads_total = db.query(func.count(UploadedFile.id)).scalar() or 0
    uploads_by_status = dict(
        db.query(UploadedFile.upload_status, func.count(UploadedFile.id))
        .group_by(UploadedFile.upload_status)
        .all()
    )

    return StatsResponse(
        users_total=users_total,
        users_active=users_active,
        users_new_30d=users_new_30d,
        users_admins=role_counts.get("admin", 0),
        users_master_admins=role_counts.get("master_admin", 0),
        projects_total=projects_total,
        projects_by_status={k: int(v) for k, v in projects_by_status.items()},
        projects_new_30d=projects_new_30d,
        entities_total=entities_total,
        entities_by_type={k: int(v) for k, v in entities_by_type.items()},
        historical_rows=historical_rows,
        uploads_total=uploads_total,
        uploads_validated=uploads_by_status.get("validated", 0),
        uploads_rejected=uploads_by_status.get("rejected", 0),
        uploads_pending=uploads_by_status.get("pending", 0),
        timestamp=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

@router.get("/users", response_model=AdminUserListResponse)
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
    q: Optional[str] = Query(None, description="Email or name substring (case-insensitive)"),
    role: Optional[Literal["user", "admin", "master_admin"]] = None,
    include_deleted: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
) -> AdminUserListResponse:
    query = db.query(User)
    if not include_deleted:
        query = query.filter(User.deleted_at.is_(None))
    if role:
        query = query.filter(User.role == role)
    if q:
        like = f"%{q.lower()}%"
        query = query.filter(
            (func.lower(User.email).like(like)) | (func.lower(User.name).like(like))
        )

    total = query.count()
    rows = (
        query.order_by(User.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    user_ids = [u.id for u in rows]
    project_counts: dict[str, int] = {}
    if user_ids:
        for uid, count in (
            db.query(Project.user_id, func.count(Project.id))
            .filter(Project.user_id.in_(user_ids))
            .group_by(Project.user_id)
            .all()
        ):
            project_counts[uid] = int(count)

    items = [
        AdminUserOut(
            id=u.id,
            email=u.email,
            name=u.name,
            role=u.role,
            auth_provider=u.auth_provider,
            created_at=u.created_at,
            deleted_at=u.deleted_at,
            project_count=project_counts.get(u.id, 0),
        )
        for u in rows
    ]
    return AdminUserListResponse(items=items, total=total, page=page, page_size=page_size)


@router.patch("/users/{user_id}", response_model=AdminUserOut)
def update_user(
    user_id: str,
    payload: UpdateUserRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_master_admin),
) -> AdminUserOut:
    """Master-admin-only: change role, soft-delete, or restore a user."""
    if user_id == current_user.id:
        # Prevent the master_admin from accidentally locking themselves out.
        raise HTTPException(
            status_code=400, detail="Master admins cannot mutate their own account here.",
        )

    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    changed = False

    if payload.role is not None and target.role != payload.role:
        target.role = payload.role
        changed = True

    if payload.deactivate is True and target.deleted_at is None:
        now = datetime.now(timezone.utc)
        target.deleted_at = now
        # Bump password_changed_at so any cached tokens are immediately killed.
        target.password_changed_at = now
        changed = True
    elif payload.deactivate is False and target.deleted_at is not None:
        target.deleted_at = None
        changed = True

    if changed:
        db.commit()
        db.refresh(target)

    project_count = (
        db.query(func.count(Project.id))
        .filter(Project.user_id == target.id)
        .scalar()
        or 0
    )

    return AdminUserOut(
        id=target.id,
        email=target.email,
        name=target.name,
        role=target.role,
        auth_provider=target.auth_provider,
        created_at=target.created_at,
        deleted_at=target.deleted_at,
        project_count=int(project_count),
    )
