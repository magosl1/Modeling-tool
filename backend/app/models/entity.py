"""Entity model — the fundamental modeling unit for the universal platform."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, backref, mapped_column, relationship

from app.db.base import Base


class Entity(Base):
    """
    An Entity is the fundamental modeling unit. It represents anything
    that has its own set of financial statements:
    - A listed company
    - A private company
    - A biogas plant / investment project
    - A business division
    - A real estate asset
    - A holding company
    """
    __tablename__ = "entities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parent_entity_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("entities.id", ondelete="SET NULL"), nullable=True
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    entity_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="company_private"
        # Values: "company_listed" | "company_private" | "project" | "division" | "asset" | "holdco"
    )

    # Only for entity_type = "company_listed"
    ticker: Mapped[str | None] = mapped_column(String(20), nullable=True)
    exchange: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Entity metadata
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="EUR")
    country: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sector: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    # Ownership / consolidation
    ownership_pct: Mapped[float] = mapped_column(Float, nullable=False, default=100.0)
    consolidation_method: Mapped[str] = mapped_column(
        String(20), nullable=False, default="full"
        # Values: "full" | "proportional" | "equity_method" | "none"
    )

    # Status and lifecycle
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    start_date: Mapped[str | None] = mapped_column(String(10), nullable=True)  # "YYYY-MM-DD"
    end_date: Mapped[str | None] = mapped_column(String(10), nullable=True)    # "YYYY-MM-DD"

    display_order: Mapped[int] = mapped_column(nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Back-reference to Project
    project: Mapped["Project"] = relationship(  # type: ignore[name-defined]
        "Project", back_populates="entities", foreign_keys=[project_id]
    )

    # Self-referential relationship for hierarchy.
    # remote_side on the parent side tells SQLAlchemy this is the many-to-one direction.
    children: Mapped[list["Entity"]] = relationship(
        "Entity",
        backref=backref("parent", remote_side="Entity.id"),
        foreign_keys=[parent_entity_id],
        lazy="select",
    )
