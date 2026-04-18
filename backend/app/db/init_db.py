"""Initialize database tables."""
from pathlib import Path

from alembic import command
from alembic.config import Config

from app.db.base import Base, engine
from app.models.user import User
from app.models.entity import Entity  # noqa: F401 — registers table with metadata
from app.models.eliminations import IntercompanyTransaction  # noqa: F401
from app.models.project import (
    Project, Scenario, HistoricalData, RevenueStream, RevenueStreamParam,
    ProjectionAssumption, AssumptionParam, NOLBalance,
    ProjectedFinancial, ValuationInput, ValuationOutput, UploadedFile,
    RevolverConfig, DebtTranche, FXRate, SimulationResult, ProjectShare,
    ExternalCurveValue,
)


def _alembic_config() -> Config:
    ini_path = Path(__file__).resolve().parents[2] / "alembic.ini"
    return Config(str(ini_path))


def create_tables():
    Base.metadata.create_all(bind=engine)
    # Stamp the baseline so Alembic knows future revisions start from here.
    command.stamp(_alembic_config(), "head")


if __name__ == "__main__":
    create_tables()
    print("Database tables created successfully.")
