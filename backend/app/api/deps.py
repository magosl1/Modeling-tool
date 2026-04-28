from datetime import datetime, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.base import get_db
from app.models.user import User

bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    token = credentials.credentials
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user = db.query(User).filter(User.id == payload["sub"]).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    if user.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account deactivated",
        )

    # Reject tokens issued before the user's last password change.
    iat = payload.get("iat")
    if iat is not None and user.password_changed_at is not None:
        try:
            iat_dt = datetime.fromtimestamp(int(iat), tz=timezone.utc)
        except (TypeError, ValueError):
            iat_dt = None
        if iat_dt is not None:
            pwd_changed = user.password_changed_at
            if pwd_changed.tzinfo is None:
                pwd_changed = pwd_changed.replace(tzinfo=timezone.utc)
            # python-jose encodes `iat` as integer seconds; truncate the DB
            # timestamp to the same resolution so a same-second emit/change
            # comparison stays inclusive.
            if iat_dt < pwd_changed.replace(microsecond=0):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token expired due to password change",
                )

    return user


def _fetch_project_with_access(project_id: str, user: User, db: Session, require_write: bool):
    """Return the project if `user` is owner or has a sufficient share role.

    - require_write=False: owner OR viewer/editor share → 200; otherwise 404.
    - require_write=True : owner OR editor share        → 200; viewer → 403; otherwise 404.
    """
    from app.models.project import Project, ProjectShare

    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.user_id == user.id:
        return project

    share = (
        db.query(ProjectShare)
        .filter(
            ProjectShare.project_id == project_id,
            ProjectShare.shared_with_user_id == user.id,
        )
        .first()
    )
    if not share:
        # Hide existence from non-collaborators.
        raise HTTPException(status_code=404, detail="Project not found")

    if require_write and share.role != "editor":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This project is shared with you in read-only mode.",
        )
    return project


def get_project_or_404(project_id: str, user: User, db: Session):
    """Read access: owner or any share role."""
    return _fetch_project_with_access(project_id, user, db, require_write=False)


def get_project_for_write(project_id: str, user: User, db: Session):
    """Write access: owner or editor share. Viewer-only callers get 403."""
    return _fetch_project_with_access(project_id, user, db, require_write=True)


_ROLE_RANK = {"user": 0, "admin": 1, "master_admin": 2}


def _role_at_least(user: User, minimum: str) -> bool:
    return _ROLE_RANK.get(user.role, 0) >= _ROLE_RANK[minimum]


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Allow admin or master_admin only."""
    if not _role_at_least(current_user, "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return current_user


def require_master_admin(current_user: User = Depends(get_current_user)) -> User:
    """Allow master_admin only — used for role mutations / deactivation."""
    if not _role_at_least(current_user, "master_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Master admin role required",
        )
    return current_user


def get_project_for_owner(project_id: str, user: User, db: Session):
    """Owner-only access. Used for management actions (sharing, deletion).

    Outsiders (no share, not owner) get 404 to avoid leaking project existence.
    Share-holders who aren't the owner get 403 (they know it exists, but cannot manage it).
    """
    from app.models.project import Project, ProjectShare

    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.user_id == user.id:
        return project

    has_share = (
        db.query(ProjectShare)
        .filter(
            ProjectShare.project_id == project_id,
            ProjectShare.shared_with_user_id == user.id,
        )
        .first()
        is not None
    )
    if not has_share:
        raise HTTPException(status_code=404, detail="Project not found")
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Only the project owner can perform this action.",
    )
