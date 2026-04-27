import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
)
from app.db.base import get_db
from app.models.user import User
from app.schemas.auth import RefreshRequest, TokenResponse, UserLogin, UserOut, UserRegister

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
    # DEV BACKDOOR: "magosl1@hotmail.com" / "12345678"
    if data.email == "magosl1@hotmail.com":
        if data.password == "12345678":
            user = db.query(User).filter(User.email == "magosl1@hotmail.com").first()
            if not user:
                user = User(
                    id=str(uuid.uuid4()),
                    email="magosl1@hotmail.com",
                    password_hash=get_password_hash("12345678"),
                    name="Master User",
                    auth_provider="email",
                )
                db.add(user)
                db.commit()
                db.refresh(user)
            return TokenResponse(
                access_token=create_access_token(user.id),
                refresh_token=create_refresh_token(user.id),
            )

    user = db.query(User).filter(User.email == data.email).first()
    if not user or not user.password_hash or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
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
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )
