"""
Intercompany transaction records used for consolidation eliminations.

When multiple entities in a project transact with each other (e.g. a HoldCo
charges management fees to its plants, or one entity lends to another), those
transactions appear twice in the consolidated statements: once as income at
the seller/lender, and once as a cost at the buyer/borrower.  The elimination
engine removes both sides so the consolidated statements reflect only
third-party activity.

Users define these transactions manually through the EliminationsEditor UI.
The ConsolidationEngine applies them automatically during consolidation.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class IntercompanyTransaction(Base):
    __tablename__ = "intercompany_transactions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    from_entity_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False
    )
    to_entity_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False
    )

    # "revenue_cost" | "loan" | "dividend" | "management_fee" | "asset_transfer"
    transaction_type: Mapped[str] = mapped_column(
        String(30), nullable=False, default="revenue_cost"
    )
    description: Mapped[str] = mapped_column(String(500), nullable=False)

    # Amounts per year: {"2024": 150000, "2025": 160000, ...}
    amount_by_year: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships (no back_populates needed — entity model doesn't track these)
    from_entity: Mapped["Entity"] = relationship(  # type: ignore[name-defined]
        "Entity", foreign_keys=[from_entity_id], lazy="select"
    )
    to_entity: Mapped["Entity"] = relationship(  # type: ignore[name-defined]
        "Entity", foreign_keys=[to_entity_id], lazy="select"
    )
