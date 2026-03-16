"""Initialize database tables."""
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


def create_tables():
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    create_tables()
    print("Database tables created successfully.")
