"""Tests for the admin RBAC helpers (Fase 0.5.2).

Verifies require_admin / require_master_admin role gates without spinning
up FastAPI; calls the dependency functions directly with synthetic users.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.deps import _role_at_least, require_admin, require_master_admin
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


def _make_user(role: str = "user") -> User:
    now = datetime.now(timezone.utc)
    return User(
        id=str(uuid.uuid4()),
        email=f"{role}@example.com",
        password_hash="x",
        name=role,
        auth_provider="email",
        role=role,
        created_at=now,
        updated_at=now,
        password_changed_at=now,
    )


class TestRoleHierarchy:
    @pytest.mark.parametrize("role,minimum,expected", [
        ("user", "user", True),
        ("user", "admin", False),
        ("user", "master_admin", False),
        ("admin", "user", True),
        ("admin", "admin", True),
        ("admin", "master_admin", False),
        ("master_admin", "user", True),
        ("master_admin", "admin", True),
        ("master_admin", "master_admin", True),
    ])
    def test_at_least(self, role, minimum, expected):
        u = _make_user(role)
        assert _role_at_least(u, minimum) is expected


class TestRequireAdmin:
    def test_user_blocked(self):
        with pytest.raises(HTTPException) as exc:
            require_admin(current_user=_make_user("user"))
        assert exc.value.status_code == 403

    def test_admin_allowed(self):
        u = _make_user("admin")
        assert require_admin(current_user=u) is u

    def test_master_admin_allowed(self):
        u = _make_user("master_admin")
        assert require_admin(current_user=u) is u


class TestRequireMasterAdmin:
    def test_user_blocked(self):
        with pytest.raises(HTTPException) as exc:
            require_master_admin(current_user=_make_user("user"))
        assert exc.value.status_code == 403

    def test_admin_blocked(self):
        with pytest.raises(HTTPException) as exc:
            require_master_admin(current_user=_make_user("admin"))
        assert exc.value.status_code == 403

    def test_master_admin_allowed(self):
        u = _make_user("master_admin")
        assert require_master_admin(current_user=u) is u


class TestMasterAdminBootstrap:
    """The /auth/login + /auth/register paths use _promote_if_master_admin to
    bootstrap the configured master admin from env. Test the helper in isolation."""

    def test_promote_when_email_matches(self, db, monkeypatch):
        from app.api.routes.auth import _promote_if_master_admin
        from app.core import config as cfg

        monkeypatch.setattr(cfg.settings, "MASTER_ADMIN_EMAIL", "boss@example.com")

        u = User(
            id=str(uuid.uuid4()),
            email="boss@example.com",
            password_hash="x",
            name="Boss",
            auth_provider="email",
            role="user",
            password_changed_at=datetime.now(timezone.utc),
        )
        db.add(u)
        db.commit()

        _promote_if_master_admin(u, db)
        db.refresh(u)
        assert u.role == "master_admin"

    def test_no_promotion_when_email_differs(self, db, monkeypatch):
        from app.api.routes.auth import _promote_if_master_admin
        from app.core import config as cfg

        monkeypatch.setattr(cfg.settings, "MASTER_ADMIN_EMAIL", "boss@example.com")

        u = User(
            id=str(uuid.uuid4()),
            email="alice@example.com",
            password_hash="x",
            name="Alice",
            auth_provider="email",
            role="user",
            password_changed_at=datetime.now(timezone.utc),
        )
        db.add(u)
        db.commit()

        _promote_if_master_admin(u, db)
        db.refresh(u)
        assert u.role == "user"

    def test_promotion_is_idempotent(self, db, monkeypatch):
        from app.api.routes.auth import _promote_if_master_admin
        from app.core import config as cfg

        monkeypatch.setattr(cfg.settings, "MASTER_ADMIN_EMAIL", "boss@example.com")

        u = User(
            id=str(uuid.uuid4()),
            email="boss@example.com",
            password_hash="x",
            name="Boss",
            auth_provider="email",
            role="master_admin",
            password_changed_at=datetime.now(timezone.utc),
        )
        db.add(u)
        db.commit()

        _promote_if_master_admin(u, db)
        _promote_if_master_admin(u, db)  # called again — must remain master_admin
        db.refresh(u)
        assert u.role == "master_admin"

    def test_no_master_admin_email_configured_no_op(self, db, monkeypatch):
        from app.api.routes.auth import _promote_if_master_admin
        from app.core import config as cfg

        monkeypatch.setattr(cfg.settings, "MASTER_ADMIN_EMAIL", None)

        u = User(
            id=str(uuid.uuid4()),
            email="anyone@example.com",
            password_hash="x",
            name="Anyone",
            auth_provider="email",
            role="user",
            password_changed_at=datetime.now(timezone.utc),
        )
        db.add(u)
        db.commit()

        _promote_if_master_admin(u, db)
        db.refresh(u)
        assert u.role == "user"

    def test_email_match_is_case_insensitive(self, db, monkeypatch):
        from app.api.routes.auth import _promote_if_master_admin
        from app.core import config as cfg

        monkeypatch.setattr(cfg.settings, "MASTER_ADMIN_EMAIL", "Boss@Example.com")

        u = User(
            id=str(uuid.uuid4()),
            email="boss@example.com",
            password_hash="x",
            name="Boss",
            auth_provider="email",
            role="user",
            password_changed_at=datetime.now(timezone.utc),
        )
        db.add(u)
        db.commit()

        _promote_if_master_admin(u, db)
        db.refresh(u)
        assert u.role == "master_admin"
