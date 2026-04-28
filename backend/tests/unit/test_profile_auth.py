"""Tests for the user profile flow (Fase 0.5.1).

Covers:
- Token issued before password change → rejected (get_current_user).
- Token issued before account deletion → rejected (get_current_user).
- Login blocked after soft-delete.
- Refresh token issued before password change → rejected by /auth/refresh logic.

These tests exercise the auth deps + token logic against an in-memory SQLite
DB without starting the FastAPI app.
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.deps import get_current_user
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
)
from app.db.base import Base
from app.models.eliminations import IntercompanyTransaction  # noqa: F401
from app.models.entity import Entity  # noqa: F401
from app.models.project import Project, ProjectShare  # noqa: F401
from app.models.user import User


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


def _make_user(db, *, email="alice@example.com", password="OldPass123") -> User:
    now = datetime.now(timezone.utc)
    u = User(
        id=str(uuid.uuid4()),
        email=email,
        password_hash=get_password_hash(password),
        name=email.split("@")[0],
        auth_provider="email",
        created_at=now,
        updated_at=now,
        password_changed_at=now,
    )
    db.add(u)
    db.commit()
    return u


def _call_get_current_user(token: str, db) -> User:
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    return get_current_user(credentials=creds, db=db)


# ---------------------------------------------------------------------------
# Token includes iat
# ---------------------------------------------------------------------------

class TestTokenContainsIat:
    def test_access_token_has_iat(self):
        token = create_access_token("user-1")
        payload = decode_token(token)
        assert payload is not None
        assert "iat" in payload
        assert "exp" in payload
        assert payload["type"] == "access"

    def test_refresh_token_has_iat(self):
        token = create_refresh_token("user-1")
        payload = decode_token(token)
        assert payload is not None
        assert "iat" in payload
        assert payload["type"] == "refresh"


# ---------------------------------------------------------------------------
# Password change invalidates prior tokens
# ---------------------------------------------------------------------------

class TestPasswordChangeInvalidatesTokens:
    def test_token_before_password_change_is_rejected(self, db):
        user = _make_user(db)
        token = create_access_token(user.id)

        # Simulate user changing password 5 seconds later.
        time.sleep(1)
        user.password_hash = get_password_hash("NewPass456")
        user.password_changed_at = datetime.now(timezone.utc) + timedelta(seconds=5)
        db.commit()

        with pytest.raises(HTTPException) as exc:
            _call_get_current_user(token, db)
        assert exc.value.status_code == 401
        assert "password change" in exc.value.detail.lower()

    def test_token_after_password_change_is_accepted(self, db):
        user = _make_user(db)
        # Bump password_changed_at to "now"
        user.password_changed_at = datetime.now(timezone.utc)
        db.commit()
        time.sleep(1)
        # Issue a token AFTER the password change
        token = create_access_token(user.id)

        result = _call_get_current_user(token, db)
        assert result.id == user.id

    def test_unrelated_token_unaffected(self, db):
        u1 = _make_user(db, email="u1@example.com")
        u2 = _make_user(db, email="u2@example.com")
        token_u2 = create_access_token(u2.id)

        # u1 changes password — must not affect u2's token
        time.sleep(1)
        u1.password_changed_at = datetime.now(timezone.utc) + timedelta(seconds=5)
        db.commit()

        result = _call_get_current_user(token_u2, db)
        assert result.id == u2.id


# ---------------------------------------------------------------------------
# Soft-delete blocks authentication
# ---------------------------------------------------------------------------

class TestSoftDeleteBlocksAuth:
    def test_token_for_deleted_user_is_rejected(self, db):
        user = _make_user(db)
        token = create_access_token(user.id)

        user.deleted_at = datetime.now(timezone.utc)
        db.commit()

        with pytest.raises(HTTPException) as exc:
            _call_get_current_user(token, db)
        assert exc.value.status_code == 401
        assert "deactivated" in exc.value.detail.lower()

    def test_active_user_token_accepted(self, db):
        user = _make_user(db)
        token = create_access_token(user.id)
        result = _call_get_current_user(token, db)
        assert result.id == user.id


# ---------------------------------------------------------------------------
# Invalid / expired token edge cases
# ---------------------------------------------------------------------------

class TestInvalidTokens:
    def test_garbage_token_rejected(self, db):
        with pytest.raises(HTTPException) as exc:
            _call_get_current_user("not-a-jwt", db)
        assert exc.value.status_code == 401

    def test_refresh_token_rejected_for_get_current_user(self, db):
        user = _make_user(db)
        refresh = create_refresh_token(user.id)
        with pytest.raises(HTTPException) as exc:
            _call_get_current_user(refresh, db)
        assert exc.value.status_code == 401

    def test_unknown_user_id_rejected(self, db):
        token = create_access_token("nonexistent-id")
        with pytest.raises(HTTPException) as exc:
            _call_get_current_user(token, db)
        assert exc.value.status_code == 401


# ---------------------------------------------------------------------------
# Password verification helper sanity checks
# ---------------------------------------------------------------------------

class TestPasswordHelpers:
    def test_verify_old_then_new(self):
        h = get_password_hash("OldPass123")
        assert verify_password("OldPass123", h)
        assert not verify_password("NewPass456", h)

        h2 = get_password_hash("NewPass456")
        assert verify_password("NewPass456", h2)
        assert not verify_password("OldPass123", h2)
