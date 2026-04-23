"""Tests for the RBAC helpers in app.api.deps.

Uses SQLite in-memory to verify owner / editor / viewer / outsider semantics
without spinning up the full FastAPI app.
"""
import uuid
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.deps import (
    get_project_for_owner,
    get_project_for_write,
    get_project_or_404,
)
from app.db.base import Base
from app.models.eliminations import IntercompanyTransaction  # noqa: F401
from app.models.entity import Entity  # noqa: F401 — register tables
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


def _make_user(db, email):
    u = User(
        id=str(uuid.uuid4()),
        email=email,
        password_hash="x",
        name=email.split("@")[0],
        auth_provider="email",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(u)
    db.commit()
    return u


def _make_project(db, owner_id):
    p = Project(
        id=str(uuid.uuid4()),
        user_id=owner_id,
        name="Test",
        currency="USD",
        scale="thousands",
        projection_years=5,
        status="draft",
    )
    db.add(p)
    db.commit()
    return p


def _share(db, project_id, user_id, role):
    s = ProjectShare(
        id=str(uuid.uuid4()),
        project_id=project_id,
        shared_with_user_id=user_id,
        role=role,
    )
    db.add(s)
    db.commit()


def test_owner_has_read_write_and_owner_access(db):
    owner = _make_user(db, "owner@x.com")
    project = _make_project(db, owner.id)

    assert get_project_or_404(project.id, owner, db).id == project.id
    assert get_project_for_write(project.id, owner, db).id == project.id
    assert get_project_for_owner(project.id, owner, db).id == project.id


def test_outsider_gets_404_on_all_helpers(db):
    owner = _make_user(db, "owner@x.com")
    outsider = _make_user(db, "outsider@x.com")
    project = _make_project(db, owner.id)

    for fn in (get_project_or_404, get_project_for_write, get_project_for_owner):
        with pytest.raises(HTTPException) as exc:
            fn(project.id, outsider, db)
        assert exc.value.status_code == 404


def test_viewer_can_read_but_not_write_or_own(db):
    owner = _make_user(db, "owner@x.com")
    viewer = _make_user(db, "viewer@x.com")
    project = _make_project(db, owner.id)
    _share(db, project.id, viewer.id, "viewer")

    assert get_project_or_404(project.id, viewer, db).id == project.id

    with pytest.raises(HTTPException) as exc:
        get_project_for_write(project.id, viewer, db)
    assert exc.value.status_code == 403

    with pytest.raises(HTTPException) as exc:
        get_project_for_owner(project.id, viewer, db)
    assert exc.value.status_code == 403


def test_editor_can_read_and_write_but_not_own(db):
    owner = _make_user(db, "owner@x.com")
    editor = _make_user(db, "editor@x.com")
    project = _make_project(db, owner.id)
    _share(db, project.id, editor.id, "editor")

    assert get_project_or_404(project.id, editor, db).id == project.id
    assert get_project_for_write(project.id, editor, db).id == project.id

    with pytest.raises(HTTPException) as exc:
        get_project_for_owner(project.id, editor, db)
    assert exc.value.status_code == 403
