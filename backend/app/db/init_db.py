"""Initialize database tables."""
from app.db.base import Base, engine
from app.models.user import User
from app.models.project import (
    Project, HistoricalData, RevenueStream, RevenueStreamParam,
    ProjectionAssumption, AssumptionParam, NOLBalance,
    ProjectedFinancial, ValuationInput, ValuationOutput, UploadedFile,
)


def create_tables():
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    create_tables()
    print("Database tables created successfully.")
