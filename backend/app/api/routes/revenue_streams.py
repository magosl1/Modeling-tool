"""
Revenue stream configuration routes.

Manages the revenue line definitions for a project — the list of named
revenue sub-lines (e.g., "Venta Energía", "Venta Fertilizante", "Venta CO2")
that determine:
  1. What rows appear in the downloaded historical template
  2. How historical revenue data is stored (per sub-line)
  3. What projection streams appear in the Assumptions → Revenue module

Each revenue stream is stored as a RevenueStream record (scenario_id=NULL
= base config).  Projection assumptions for each stream are auto-created /
kept in sync whenever the stream list is saved.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import uuid

from app.db.base import get_db
from app.models.user import User
from app.models.project import RevenueStream, ProjectionAssumption
from app.api.deps import get_current_user, get_project_or_404
from app.services.historical_validator import STANDARD_PNL_ITEMS  # single source of truth

router = APIRouter(prefix="/projects", tags=["revenue-streams"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _sync_revenue_assumptions(project_id: str, stream_names: List[str], db: Session):
    """
    Keep ProjectionAssumption records for module='revenue' in sync with streams.

    - Add assumptions for new streams (default method: growth_flat)
    - Remove assumptions for deleted streams
    - Preserve existing assumptions (method + params) for unchanged streams
    """
    existing = {
        a.line_item: a
        for a in db.query(ProjectionAssumption).filter(
            ProjectionAssumption.project_id == project_id,
            ProjectionAssumption.module == "revenue",
            ProjectionAssumption.scenario_id == None,  # noqa: E711
        ).all()
    }

    new_set = set(stream_names)
    existing_set = set(existing.keys())

    # Delete assumptions for removed streams
    for name in existing_set - new_set:
        db.delete(existing[name])

    # Add assumptions for new streams
    for name in new_set - existing_set:
        db.add(ProjectionAssumption(
            id=str(uuid.uuid4()),
            project_id=project_id,
            module="revenue",
            line_item=name,
            projection_method="growth_flat",
        ))


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/{project_id}/revenue-streams")
def get_revenue_streams(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return defined revenue streams (base config, no scenario)."""
    get_project_or_404(project_id, current_user, db)
    streams = (
        db.query(RevenueStream)
        .filter(
            RevenueStream.project_id == project_id,
            RevenueStream.scenario_id == None,  # noqa: E711
        )
        .order_by(RevenueStream.display_order)
        .all()
    )

    # If no streams defined yet, return default single-line config
    if not streams:
        return [{"stream_name": "Revenue", "display_order": 0, "projection_method": "growth_flat", "id": None}]

    return [
        {
            "id": s.id,
            "stream_name": s.stream_name,
            "display_order": s.display_order,
            "projection_method": s.projection_method,
        }
        for s in streams
    ]


@router.put("/{project_id}/revenue-streams")
def save_revenue_streams(
    project_id: str,
    streams: List[dict],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Replace all revenue stream definitions for a project.

    Body: [{"stream_name": "Venta Energía", "display_order": 0, "projection_method": "growth_flat"}, ...]

    Also keeps ProjectionAssumption records for module='revenue' in sync.
    """
    get_project_or_404(project_id, current_user, db)

    if not streams:
        raise HTTPException(400, "At least one revenue stream is required")
    if len(streams) > 50:
        raise HTTPException(400, "Maximum 50 revenue streams per project")

    for s in streams:
        if not s.get("stream_name", "").strip():
            raise HTTPException(400, "stream_name cannot be empty")

    # Delete all existing base-config streams
    db.query(RevenueStream).filter(
        RevenueStream.project_id == project_id,
        RevenueStream.scenario_id == None,  # noqa: E711
    ).delete()
    db.flush()

    stream_names = []
    for i, s in enumerate(streams):
        name = s["stream_name"].strip()
        stream_names.append(name)
        db.add(RevenueStream(
            id=str(uuid.uuid4()),
            project_id=project_id,
            scenario_id=None,
            stream_name=name,
            display_order=s.get("display_order", i),
            projection_method=s.get("projection_method", "growth_flat"),
        ))

    # Sync projection assumptions
    _sync_revenue_assumptions(project_id, stream_names, db)

    db.commit()
    return {"message": f"Saved {len(streams)} revenue stream(s)", "streams": stream_names}


@router.post("/{project_id}/revenue-streams/detect")
def detect_revenue_streams(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Detect revenue sub-lines from the already-uploaded historical data.

    Returns the list of detected revenue sub-lines with their historical values.
    Used after uploading historical data to confirm / adjust stream configuration.
    """
    from app.models.project import HistoricalData
    get_project_or_404(project_id, current_user, db)

    records = (
        db.query(HistoricalData)
        .filter(
            HistoricalData.project_id == project_id,
            HistoricalData.statement_type == "PNL",
            HistoricalData.bucket == "Revenue",
        )
        .all()
    )

    if not records:
        # No sub-lines, single Revenue line
        revenue_records = (
            db.query(HistoricalData)
            .filter(
                HistoricalData.project_id == project_id,
                HistoricalData.statement_type == "PNL",
                HistoricalData.line_item == "Revenue",
            )
            .all()
        )
        return {
            "detected_streams": [{"stream_name": "Revenue", "is_standard": True}],
            "has_sub_lines": False,
            "historical_preview": {
                r.year: str(r.value) for r in revenue_records
            },
        }

    streams_seen: dict = {}
    for r in records:
        if r.line_item not in streams_seen:
            streams_seen[r.line_item] = {}
        streams_seen[r.line_item][r.year] = str(r.value)

    return {
        "detected_streams": [
            {"stream_name": name, "is_standard": False, "historical": vals}
            for name, vals in streams_seen.items()
        ],
        "has_sub_lines": True,
    }
