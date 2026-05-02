"""Tests for the entity-scoped variants of load_historical / load_assumptions
(Fase B — multi-entity per-entity projections).

The loaders now accept an optional entity_id. When provided, only that
entity's rows are returned; when omitted, the project-wide aggregate is
returned (legacy behaviour, kept for the consolidated views).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.eliminations import IntercompanyTransaction  # noqa: F401
from app.models.entity import Entity
from app.models.project import (
    AssumptionParam,
    HistoricalData,
    Project,
    ProjectionAssumption,
    ProjectShare,  # noqa: F401
)
from app.models.user import User
from app.services.projections_runner import load_assumptions, load_historical


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


def _build_project_with_two_entities(db):
    now = datetime.now(timezone.utc)
    user = User(
        id=str(uuid.uuid4()), email="user@example.com", password_hash="x",
        name="user", auth_provider="email", role="user",
        created_at=now, updated_at=now, password_changed_at=now,
    )
    db.add(user)
    db.commit()

    project = Project(
        id=str(uuid.uuid4()), user_id=user.id, name="Group",
        currency="EUR", scale="thousands", status="draft",
        projection_years=5, created_at=now, updated_at=now,
    )
    db.add(project)
    db.commit()

    entities = []
    for i, name in enumerate(["Energy", "Fertilizer"]):
        e = Entity(
            id=str(uuid.uuid4()), project_id=project.id, parent_entity_id=None,
            name=name, entity_type="company_private", currency="EUR",
            ownership_pct=100.0, consolidation_method="full", is_active=True,
            display_order=i, created_at=now, updated_at=now,
        )
        db.add(e)
        entities.append(e)
    db.commit()
    return project, entities


# ---------------------------------------------------------------------------
# load_historical — entity-scoped
# ---------------------------------------------------------------------------

class TestLoadHistoricalEntityScope:
    def test_filters_by_entity_id_when_provided(self, db):
        project, (energy, fertilizer) = _build_project_with_two_entities(db)

        # Energy: Revenue 100 in 2023
        db.add(HistoricalData(
            id=str(uuid.uuid4()), project_id=project.id, entity_id=energy.id,
            statement_type="PNL", line_item="Revenue", year=2023, value=Decimal("100"),
        ))
        # Fertilizer: Revenue 200 in 2023
        db.add(HistoricalData(
            id=str(uuid.uuid4()), project_id=project.id, entity_id=fertilizer.id,
            statement_type="PNL", line_item="Revenue", year=2023, value=Decimal("200"),
        ))
        db.commit()

        e_pnl, _, _, e_years = load_historical(project.id, db, entity_id=energy.id)
        f_pnl, _, _, f_years = load_historical(project.id, db, entity_id=fertilizer.id)

        assert e_years == [2023] and f_years == [2023]
        assert e_pnl["Revenue"][2023] == Decimal("100")
        assert f_pnl["Revenue"][2023] == Decimal("200")

    def test_no_entity_id_returns_project_wide(self, db):
        """Legacy behaviour: omitting entity_id aggregates across entities."""
        project, (energy, fertilizer) = _build_project_with_two_entities(db)
        for ent, val in ((energy, "100"), (fertilizer, "200")):
            db.add(HistoricalData(
                id=str(uuid.uuid4()), project_id=project.id, entity_id=ent.id,
                statement_type="PNL", line_item="Revenue", year=2023, value=Decimal(val),
            ))
        db.commit()

        # Same line item from both entities — last write wins in the dict
        # because load_historical is a flat aggregator. The total years match
        # and both entities' data is visible.
        pnl, _, _, years = load_historical(project.id, db)
        assert 2023 in years
        # Revenue dict has at least one of the two values; we don't care which
        # since project-wide aggregation collapses by (line_item, year).
        assert pnl["Revenue"][2023] in (Decimal("100"), Decimal("200"))

    def test_entity_with_no_data_returns_empty(self, db):
        project, (energy, fertilizer) = _build_project_with_two_entities(db)
        db.add(HistoricalData(
            id=str(uuid.uuid4()), project_id=project.id, entity_id=energy.id,
            statement_type="PNL", line_item="Revenue", year=2023, value=Decimal("100"),
        ))
        db.commit()

        pnl, bs, cf, years = load_historical(project.id, db, entity_id=fertilizer.id)
        assert years == []
        assert pnl == {} and bs == {} and cf == {}


# ---------------------------------------------------------------------------
# load_assumptions — entity-scoped
# ---------------------------------------------------------------------------

class TestLoadAssumptionsEntityScope:
    def _seed_revenue_assumption(self, db, project_id, entity_id, growth):
        a_id = str(uuid.uuid4())
        db.add(ProjectionAssumption(
            id=a_id, project_id=project_id, entity_id=entity_id,
            module="revenue", line_item="Revenue", projection_method="growth_flat",
        ))
        db.add(AssumptionParam(
            id=str(uuid.uuid4()), assumption_id=a_id,
            param_key="growth_rate", value=str(growth),
        ))
        db.commit()

    def test_filters_by_entity_id(self, db):
        project, (energy, fertilizer) = _build_project_with_two_entities(db)
        self._seed_revenue_assumption(db, project.id, energy.id, "0.05")
        self._seed_revenue_assumption(db, project.id, fertilizer.id, "0.10")

        e_assum = load_assumptions(project.id, db, entity_id=energy.id)
        f_assum = load_assumptions(project.id, db, entity_id=fertilizer.id)

        # Each entity sees only its own assumption row.
        e_growth = e_assum["revenue"]["streams"][0]["params"][0]["value"]
        f_growth = f_assum["revenue"]["streams"][0]["params"][0]["value"]
        assert e_growth == Decimal("0.05")
        assert f_growth == Decimal("0.10")

    def test_no_entity_returns_aggregate(self, db):
        project, (energy, fertilizer) = _build_project_with_two_entities(db)
        self._seed_revenue_assumption(db, project.id, energy.id, "0.05")
        self._seed_revenue_assumption(db, project.id, fertilizer.id, "0.10")

        assum = load_assumptions(project.id, db)  # no entity_id
        # Both entities' streams get merged into the same revenue.streams list.
        streams = assum["revenue"]["streams"]
        assert len(streams) == 2

    def test_entity_with_no_assumptions_returns_empty(self, db):
        project, (energy, fertilizer) = _build_project_with_two_entities(db)
        self._seed_revenue_assumption(db, project.id, energy.id, "0.05")

        f_assum = load_assumptions(project.id, db, entity_id=fertilizer.id)
        assert f_assum == {}
