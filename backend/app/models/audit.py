"""Audit / change-log model.

Every mutation on the four critical entity types is recorded here:
  - 'assumption'  → ProjectionAssumption + AssumptionParam
  - 'historical'  → HistoricalData (bulk saves create one entry per statement)
  - 'scenario'    → Scenario
  - 'valuation'   → ValuationInput

The table is append-only (no UPDATE/DELETE ever issued against it).
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ChangeLog(Base):
    __tablename__ = "change_log"
    __table_args__ = (
        Index("ix_change_log_project_created", "project_id", "created_at"),
        Index("ix_change_log_entity", "entity", "entity_id"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # High-level entity type — drives UI icon and filter pills
    entity: Mapped[str] = mapped_column(String(50), nullable=False)
    # PK of the changed row (assumption id, scenario id, …)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    # 'create' | 'update' | 'delete'
    action: Mapped[str] = mapped_column(String(10), nullable=False)
    # Human-readable summary generated at write time, e.g.
    # "Revenue · growth_rate: 8.0% → 10.0%"
    summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Full state snapshots — nullable so creates only need after_json
    before_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True
    )
