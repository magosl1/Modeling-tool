import uuid
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import String, DateTime, Integer, Date, Enum as SAEnum, ForeignKey, Numeric, UniqueConstraint, Index, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
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
    # Phase 0: Universal platform fields
    project_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="single_entity"
        # Values: "single_entity" | "multi_entity" | "project_finance"
    )
    base_currency: Mapped[str] = mapped_column(String(10), nullable=False, default="USD")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    entities: Mapped[list["Entity"]] = relationship(  # type: ignore[name-defined]
        "Entity", back_populates="project", cascade="all, delete-orphan",
        order_by="Entity.display_order"
    )
    historical_data: Mapped[list["HistoricalData"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    assumptions: Mapped[list["ProjectionAssumption"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    projected_financials: Mapped[list["ProjectedFinancial"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    nol_balances: Mapped[list["NOLBalance"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    valuation_input: Mapped["ValuationInput | None"] = relationship(back_populates="project", cascade="all, delete-orphan", uselist=False)
    valuation_output: Mapped["ValuationOutput | None"] = relationship(back_populates="project", cascade="all, delete-orphan", uselist=False)


class Scenario(Base):
    __tablename__ = "scenarios"
    __table_args__ = (
        UniqueConstraint("project_id", "name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_base: Mapped[bool] = mapped_column(nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class HistoricalData(Base):
    __tablename__ = "historical_data"
    __table_args__ = (
        # entity_id is included so multiple entities in the same project can each have
        # the same line_item/year without violating uniqueness.
        # NULL entity_id is allowed for legacy single-entity rows (NULL != NULL in PG).
        UniqueConstraint("project_id", "entity_id", "statement_type", "line_item", "year",
                         name="uq_historical_data_entity"),
        Index("ix_historical_data_project_id", "project_id"),
        Index("ix_historical_data_entity_id", "entity_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"))
    # Phase 0: entity_id — set for all new records; legacy records use project_id only
    entity_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("entities.id", ondelete="CASCADE"), nullable=True, index=True
    )
    statement_type: Mapped[str] = mapped_column(
        SAEnum("PNL", "BS", "CF", name="statement_type_enum"), nullable=False
    )
    line_item: Mapped[str] = mapped_column(String(100), nullable=False)
    bucket: Mapped[str | None] = mapped_column(String(50), nullable=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)

    project: Mapped["Project"] = relationship(back_populates="historical_data")


class RevenueStream(Base):
    __tablename__ = "revenue_streams"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"))
    scenario_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("scenarios.id", ondelete="CASCADE"), nullable=True)
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
    __table_args__ = (
        Index("ix_projection_assumptions_project_id", "project_id"),
        Index("ix_projection_assumptions_entity_id", "entity_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"))
    # Phase 0: entity_id — set for all new records; legacy records use project_id only
    entity_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("entities.id", ondelete="CASCADE"), nullable=True, index=True
    )
    scenario_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("scenarios.id", ondelete="CASCADE"), nullable=True)
    module: Mapped[str] = mapped_column(
        SAEnum("revenue", "cogs", "opex", "da", "working_capital", "capex", "debt", "tax",
               "dividends", "interest_income", "non_operating", name="module_enum"),
        nullable=False
    )
    line_item: Mapped[str] = mapped_column(String(100), nullable=False)
    projection_method: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    project: Mapped["Project"] = relationship(back_populates="assumptions")
    params: Mapped[list["AssumptionParam"]] = relationship(back_populates="assumption", cascade="all, delete-orphan")


class AssumptionParam(Base):
    __tablename__ = "assumption_params"
    __table_args__ = (
        UniqueConstraint("assumption_id", "param_key", "year"),
        Index("ix_assumption_params_assumption_id", "assumption_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    assumption_id: Mapped[str] = mapped_column(String(36), ForeignKey("projection_assumptions.id", ondelete="CASCADE"))
    param_key: Mapped[str] = mapped_column(String(50), nullable=False)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    value: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)

    assumption: Mapped["ProjectionAssumption"] = relationship(back_populates="params")


class NOLBalance(Base):
    __tablename__ = "nol_balances"
    __table_args__ = (
        UniqueConstraint("project_id", "scenario_id", "year"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"))
    scenario_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("scenarios.id", ondelete="CASCADE"), nullable=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    nol_opening: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False, default=0)
    nol_used: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False, default=0)
    nol_closing: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False, default=0)

    project: Mapped["Project"] = relationship(back_populates="nol_balances")


class ProjectedFinancial(Base):
    __tablename__ = "projected_financials"
    __table_args__ = (
        # entity_id included so multiple entities can store projections for the same year/line.
        UniqueConstraint("project_id", "entity_id", "scenario_id", "statement_type", "line_item", "year",
                         name="uq_projected_financials_entity"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"))
    # Phase 0: entity_id — set for all new records; legacy records use project_id only
    entity_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("entities.id", ondelete="CASCADE"), nullable=True, index=True
    )
    scenario_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("scenarios.id", ondelete="CASCADE"), nullable=True)
    statement_type: Mapped[str] = mapped_column(
        SAEnum("PNL", "BS", "CF", name="proj_statement_type_enum"), nullable=False
    )
    line_item: Mapped[str] = mapped_column(String(100), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)

    project: Mapped["Project"] = relationship(back_populates="projected_financials")


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

    project: Mapped["Project"] = relationship(back_populates="valuation_input")


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

    project: Mapped["Project"] = relationship(back_populates="valuation_output")


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


# ---------------------------------------------------------------------------
# Block 2 — Revolver / Cash Sweep
# ---------------------------------------------------------------------------

class RevolverConfig(Base):
    __tablename__ = "revolver_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"))
    scenario_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("scenarios.id", ondelete="CASCADE"), nullable=True)
    revolver_limit: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False, default=0)
    revolver_rate: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False, default=0)
    minimum_cash_balance: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False, default=0)


class DebtTranche(Base):
    __tablename__ = "debt_tranches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"))
    scenario_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("scenarios.id", ondelete="CASCADE"), nullable=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    principal: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    maturity_year: Mapped[int] = mapped_column(Integer, nullable=False)
    amortization_method: Mapped[str] = mapped_column(
        SAEnum("bullet", "straight_line", name="amort_method_enum"), nullable=False, default="bullet"
    )
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


# ---------------------------------------------------------------------------
# Block 3 — Multi-Currency / FX Rates
# ---------------------------------------------------------------------------

class FXRate(Base):
    __tablename__ = "fx_rates"
    __table_args__ = (
        UniqueConstraint("project_id", "year"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"))
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    fx_rate: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)


# ---------------------------------------------------------------------------
# Block 4 — Monte Carlo
# ---------------------------------------------------------------------------

class SimulationResult(Base):
    __tablename__ = "simulation_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"))
    scenario_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("scenarios.id", ondelete="CASCADE"), nullable=True)
    results_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ran_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Block 5 — Collaboration / Sharing
# ---------------------------------------------------------------------------

class ProjectShare(Base):
    __tablename__ = "project_shares"
    __table_args__ = (
        UniqueConstraint("project_id", "shared_with_user_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"))
    shared_with_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(
        SAEnum("viewer", "editor", name="share_role_enum"), nullable=False, default="viewer"
    )
    invited_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Block 6 — External Curves / Indices
# ---------------------------------------------------------------------------

class ExternalCurveValue(Base):
    __tablename__ = "external_curve_values"
    __table_args__ = (
        UniqueConstraint("project_id", "curve_name", "year"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"))
    curve_name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_percentage: Mapped[bool] = mapped_column(default=False, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
