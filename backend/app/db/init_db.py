"""Initialize database tables."""
from pathlib import Path

from alembic.config import Config

from alembic import command
from app.db.base import Base, engine
from app.models.ai_settings import UserAISettings  # noqa: F401
from app.models.eliminations import IntercompanyTransaction  # noqa: F401
from app.models.entity import Entity  # noqa: F401 — registers table with metadata
from app.models.project import (
    AssumptionParam,
    DebtTranche,
    ExternalCurveValue,
    FXRate,
    HistoricalData,
    NOLBalance,
    Project,
    ProjectedFinancial,
    ProjectionAssumption,
    ProjectShare,
    RevenueStream,
    RevenueStreamParam,
    RevolverConfig,
    Scenario,
    SimulationResult,
    UploadedFile,
    ValuationInput,
    ValuationOutput,
)
from app.models.user import User


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
