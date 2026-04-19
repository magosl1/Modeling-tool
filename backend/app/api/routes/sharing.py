"""Collaboration / Sharing routes — Block 5."""
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_project_for_owner
from app.db.base import get_db
from app.models.project import Project, ProjectShare
from app.models.user import User

router = APIRouter(tags=["sharing"])


class ShareRequest(BaseModel):
    email: str
    role: str = "viewer"   # "viewer" | "editor"


class ShareOut(BaseModel):
    id: str
    project_id: str
    shared_with_user_id: str
    shared_with_email: Optional[str] = None
    role: str
    invited_at: datetime


@router.post("/projects/{project_id}/share")
def share_project(
    project_id: str,
    body: ShareRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Invite a registered user to access this project."""
    get_project_for_owner(project_id, current_user, db)

    if body.role not in ("viewer", "editor"):
        raise HTTPException(400, "Role must be 'viewer' or 'editor'")

    # Find the target user by email
    target = db.query(User).filter(User.email == body.email).first()
    if not target:
        raise HTTPException(404, f"No registered user with email '{body.email}'")

    if target.id == current_user.id:
        raise HTTPException(400, "Cannot share project with yourself")

    # Upsert share
    existing = db.query(ProjectShare).filter(
        ProjectShare.project_id == project_id,
        ProjectShare.shared_with_user_id == target.id,
    ).first()

    if existing:
        existing.role = body.role
    else:
        db.add(ProjectShare(
            id=str(uuid.uuid4()),
            project_id=project_id,
            shared_with_user_id=target.id,
            role=body.role,
        ))
    db.commit()
    return {"message": f"Project shared with {body.email} as {body.role}"}


@router.get("/projects/{project_id}/share", response_model=List[ShareOut])
def list_shares(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_project_for_owner(project_id, current_user, db)
    shares = db.query(ProjectShare).filter(ProjectShare.project_id == project_id).all()
    result = []
    for s in shares:
        user = db.query(User).filter(User.id == s.shared_with_user_id).first()
        result.append(ShareOut(
            id=s.id,
            project_id=s.project_id,
            shared_with_user_id=s.shared_with_user_id,
            shared_with_email=user.email if user else None,
            role=s.role,
            invited_at=s.invited_at,
        ))
    return result


@router.delete("/projects/{project_id}/share/{user_id}")
def revoke_share(
    project_id: str,
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_project_for_owner(project_id, current_user, db)
    share = db.query(ProjectShare).filter(
        ProjectShare.project_id == project_id,
        ProjectShare.shared_with_user_id == user_id,
    ).first()
    if not share:
        raise HTTPException(404, "Share not found")
    db.delete(share)
    db.commit()
    return {"message": "Access revoked"}


@router.get("/projects/shared-with-me")
def get_shared_projects(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all projects shared with the current user."""
    shares = db.query(ProjectShare).filter(
        ProjectShare.shared_with_user_id == current_user.id
    ).all()
    result = []
    for s in shares:
        project = db.query(Project).filter(Project.id == s.project_id).first()
        if project:
            owner = db.query(User).filter(User.id == project.user_id).first()
            result.append({
                "project_id": project.id,
                "project_name": project.name,
                "owner_email": owner.email if owner else None,
                "role": s.role,
                "invited_at": s.invited_at,
                "currency": project.currency,
                "status": project.status,
            })
    return result
