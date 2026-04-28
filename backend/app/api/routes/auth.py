import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
)
from app.db.base import get_db
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    DeleteAccountRequest,
    RefreshRequest,
    TokenResponse,
    UserLogin,
    UserOut,
    UserRegister,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(data: UserRegister, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        id=str(uuid.uuid4()),
        email=data.email,
        password_hash=get_password_hash(data.password),
        name=data.name,
        auth_provider="email",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/login", response_model=TokenResponse)
def login(data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not user.password_hash or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if user.deleted_at is not None:
        raise HTTPException(status_code=401, detail="Account deactivated")
    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh(data: RefreshRequest, db: Session = Depends(get_db)):
    payload = decode_token(data.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    user = db.query(User).filter(User.id == payload["sub"]).first()
    if not user or user.deleted_at is not None:
        raise HTTPException(status_code=401, detail="User not found")
    # If the user changed password after this refresh token was issued, reject.
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
            if iat_dt < pwd_changed.replace(microsecond=0):
                raise HTTPException(status_code=401, detail="Refresh token revoked")
    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/change-password", response_model=TokenResponse)
def change_password(
    data: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Change the current user's password.

    Requires the current password as proof. On success, all previously issued
    tokens (access + refresh) for this user are invalidated by bumping
    `password_changed_at`; new tokens are returned in the response.
    """
    if not current_user.password_hash:
        raise HTTPException(
            status_code=400,
            detail="This account uses external auth and has no password to change.",
        )
    if not verify_password(data.current_password, current_user.password_hash):
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    if data.current_password == data.new_password:
        raise HTTPException(
            status_code=400,
            detail="New password must differ from the current password",
        )

    current_user.password_hash = get_password_hash(data.new_password)
    current_user.password_changed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(current_user)

    return TokenResponse(
        access_token=create_access_token(current_user.id),
        refresh_token=create_refresh_token(current_user.id),
    )


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_account(
    data: DeleteAccountRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft-delete the current user.

    The user must re-confirm their email and password. After deletion, all
    tokens for this user are rejected and login is blocked. Data is retained
    for audit; a separate purge job can hard-delete after a retention window.
    """
    if data.email_confirmation.lower() != current_user.email.lower():
        raise HTTPException(status_code=400, detail="Email confirmation does not match")
    if not current_user.password_hash or not verify_password(data.password, current_user.password_hash):
        raise HTTPException(status_code=401, detail="Password is incorrect")

    now = datetime.now(timezone.utc)
    current_user.deleted_at = now
    # Bump password_changed_at so any cached tokens are immediately rejected.
    current_user.password_changed_at = now
    db.commit()
