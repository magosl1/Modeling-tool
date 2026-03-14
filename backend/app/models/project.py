import uuid
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import String, DateTime, Integer, Date, Enum as SAEnum, ForeignKey, Numeric, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    scale: Mapped[str] = mapped_column(
        SAEnum("units", "thousands", "millions", "billions", name="scale_enum"),
        nullable=False,
        default="thousands"
    )
    fiscal_year_end: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    projection_years: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    status: Mapped[str] = mapped_column(
        SAEnum("draft", "configured", "projected", "valued", name="project_status_enum"),
        nullable=False,
        default="draft"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )


class HistoricalData(Base):
    __tablename__ = "historical_data"
    __table_args__ = (
        UniqueConstraint("project_id", "statement_type", "line_item", "year"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"))
    statement_type: Mapped[str] = mapped_column(
        SAEnum("PNL", "BS", "CF", name="statement_type_enum"), nullable=False
    )
    line_item: Mapped[str] = mapped_column(String(100), nullable=False)
    bucket: Mapped[str | None] = mapped_column(String(50), nullable=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)


class RevenueStream(Base):
    __tablename__ = "revenue_streams"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"))
    stream_name: Mapped[str] = mapped_column(String(100), nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    projection_method: Mapped[str] = mapped_column(
        SAEnum("growth_flat", "growth_variable", "price_quantity", "fixed", "external_curve",
               name="revenue_method_enum"),
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class RevenueStreamParam(Base):
    __tablename__ = "revenue_stream_params"
    __table_args__ = (
        UniqueConstraint("stream_id", "param_key", "year"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    stream_id: Mapped[str] = mapped_column(String(36), ForeignKey("revenue_streams.id", ondelete="CASCADE"))
    param_key: Mapped[str] = mapped_column(String(50), nullable=False)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    value: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)


class ProjectionAssumption(Base):
    __tablename__ = "projection_assumptions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"))
    module: Mapped[str] = mapped_column(
        SAEnum("revenue", "cogs", "opex", "da", "working_capital", "capex", "debt", "tax",
               "dividends", "interest_income", "non_operating", name="module_enum"),
        nullable=False
    )
    line_item: Mapped[str] = mapped_column(String(100), nullable=False)
    projection_method: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class AssumptionParam(Base):
    __tablename__ = "assumption_params"
    __table_args__ = (
        UniqueConstraint("assumption_id", "param_key", "year"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    assumption_id: Mapped[str] = mapped_column(String(36), ForeignKey("projection_assumptions.id", ondelete="CASCADE"))
    param_key: Mapped[str] = mapped_column(String(50), nullable=False)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    value: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)


class NOLBalance(Base):
    __tablename__ = "nol_balances"
    __table_args__ = (
        UniqueConstraint("project_id", "year"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"))
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    nol_opening: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False, default=0)
    nol_used: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False, default=0)
    nol_closing: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False, default=0)


class ProjectedFinancial(Base):
    __tablename__ = "projected_financials"
    __table_args__ = (
        UniqueConstraint("project_id", "statement_type", "line_item", "year"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"))
    statement_type: Mapped[str] = mapped_column(
        SAEnum("PNL", "BS", "CF", name="proj_statement_type_enum"), nullable=False
    )
    line_item: Mapped[str] = mapped_column(String(100), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)


class ValuationInput(Base):
    __tablename__ = "valuation_inputs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), unique=True)
    wacc: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    terminal_growth_rate: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    exit_multiple: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    discounting_convention: Mapped[str] = mapped_column(
        SAEnum("end_of_year", "mid_year", name="discounting_enum"),
        nullable=False,
        default="end_of_year"
    )
    shares_outstanding: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)


class ValuationOutput(Base):
    __tablename__ = "valuation_outputs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), unique=True)
    enterprise_value: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    net_debt: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    equity_value: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    value_per_share: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    terminal_value: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    pv_fcffs: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    pv_terminal_value: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    method_used: Mapped[str] = mapped_column(
        SAEnum("gordon_growth", "exit_multiple", name="tv_method_enum"), nullable=False
    )


class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"))
    file_type: Mapped[str] = mapped_column(
        SAEnum("historical", "module_template", "external_curve", name="file_type_enum"), nullable=False
    )
    module: Mapped[str | None] = mapped_column(String(50), nullable=True)
    s3_key: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    upload_status: Mapped[str] = mapped_column(
        SAEnum("pending", "validated", "rejected", name="upload_status_enum"), nullable=False, default="pending"
    )
    validation_errors: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
