"""
Consolidated view routes — Phase 3.

Provides group-level financial statements and intercompany elimination CRUD
for multi-entity projects.

Endpoints
---------
GET  /projects/{id}/consolidated/projections   — consolidated statements
GET  /projects/{id}/consolidated/historical    — consolidated historical
POST /projects/{id}/eliminations               — create elimination record
GET  /projects/{id}/eliminations               — list elimination records
PUT  /projects/{id}/eliminations/{eid}         — update elimination record
DEL  /projects/{id}/eliminations/{eid}         — delete elimination record
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_project_for_write, get_project_or_404
from app.db.base import get_db
from app.models.eliminations import IntercompanyTransaction
from app.models.entity import Entity
from app.models.user import User
from app.services.consolidation_engine import consolidate

router = APIRouter(prefix="/projects", tags=["consolidated"])


# ── Helpers ────────────────────────────────────────────────────────────────

def _check_entity_belongs(entity_id: str, project_id: str, db: Session) -> None:
    e = db.query(Entity).filter(
        Entity.id == entity_id,
        Entity.project_id == project_id,
    ).first()
    if not e:
        raise HTTPException(400, f"Entity {entity_id} not found in this project")


# ── Consolidated statements ────────────────────────────────────────────────

@router.get("/{project_id}/consolidated/projections")
def get_consolidated_projections(
    project_id: str,
    scenario_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return consolidated P&L / BS / CF from entity-level projected financials.

    Falls back to historical data for entities that have not yet been projected.
    """
    get_project_or_404(project_id, current_user, db)
    return consolidate(project_id, db, scenario_id=scenario_id, use_historical=False)


@router.get("/{project_id}/consolidated/historical")
def get_consolidated_historical(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return consolidated P&L / BS / CF from entity-level historical data."""
    get_project_or_404(project_id, current_user, db)
    return consolidate(project_id, db, use_historical=True)


# ── Intercompany eliminations CRUD ─────────────────────────────────────────

@router.get("/{project_id}/eliminations")
def list_eliminations(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_project_or_404(project_id, current_user, db)
    records = (
        db.query(IntercompanyTransaction)
        .filter(IntercompanyTransaction.project_id == project_id)
        .order_by(IntercompanyTransaction.created_at)
        .all()
    )
    return [
        {
            "id": r.id,
            "from_entity_id": r.from_entity_id,
            "from_entity_name": r.from_entity.name if r.from_entity else None,
            "to_entity_id": r.to_entity_id,
            "to_entity_name": r.to_entity.name if r.to_entity else None,
            "transaction_type": r.transaction_type,
            "description": r.description,
            "amount_by_year": r.amount_by_year,
            "created_at": r.created_at.isoformat(),
            "updated_at": r.updated_at.isoformat(),
        }
        for r in records
    ]


@router.post("/{project_id}/eliminations", status_code=201)
def create_elimination(
    project_id: str,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create an intercompany elimination.

    Body::

        {
            "from_entity_id": "uuid",
            "to_entity_id": "uuid",
            "transaction_type": "revenue_cost",   // or management_fee, loan, dividend
            "description": "Management fee HoldCo → Plants",
            "amount_by_year": {"2024": 150000, "2025": 160000}
        }
    """
    get_project_for_write(project_id, current_user, db)

    for fld in ("from_entity_id", "to_entity_id", "transaction_type", "description", "amount_by_year"):
        if fld not in payload:
            raise HTTPException(400, f"Missing field: {fld}")

    _check_entity_belongs(payload["from_entity_id"], project_id, db)
    _check_entity_belongs(payload["to_entity_id"], project_id, db)

    if payload["from_entity_id"] == payload["to_entity_id"]:
        raise HTTPException(400, "from_entity_id and to_entity_id must be different")

    valid_types = {"revenue_cost", "loan", "dividend", "management_fee", "asset_transfer"}
    if payload["transaction_type"] not in valid_types:
        raise HTTPException(400, f"transaction_type must be one of {sorted(valid_types)}")

    amount_by_year = payload.get("amount_by_year", {})
    if not isinstance(amount_by_year, dict):
        raise HTTPException(400, "amount_by_year must be a JSON object {year: amount}")

    record = IntercompanyTransaction(
        id=str(uuid.uuid4()),
        project_id=project_id,
        from_entity_id=payload["from_entity_id"],
        to_entity_id=payload["to_entity_id"],
        transaction_type=payload["transaction_type"],
        description=payload["description"].strip(),
        amount_by_year={str(k): float(v) for k, v in amount_by_year.items()},
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return {"id": record.id, "message": "Elimination created"}


@router.put("/{project_id}/eliminations/{elim_id}")
def update_elimination(
    project_id: str,
    elim_id: str,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_project_for_write(project_id, current_user, db)
    record = db.query(IntercompanyTransaction).filter(
        IntercompanyTransaction.id == elim_id,
        IntercompanyTransaction.project_id == project_id,
    ).first()
    if not record:
        raise HTTPException(404, "Elimination not found")

    if "description" in payload:
        record.description = payload["description"].strip()
    if "transaction_type" in payload:
        record.transaction_type = payload["transaction_type"]
    if "amount_by_year" in payload:
        record.amount_by_year = {str(k): float(v) for k, v in payload["amount_by_year"].items()}
    if "from_entity_id" in payload:
        _check_entity_belongs(payload["from_entity_id"], project_id, db)
        record.from_entity_id = payload["from_entity_id"]
    if "to_entity_id" in payload:
        _check_entity_belongs(payload["to_entity_id"], project_id, db)
        record.to_entity_id = payload["to_entity_id"]

    record.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"id": record.id, "message": "Updated"}


@router.delete("/{project_id}/eliminations/{elim_id}", status_code=204)
def delete_elimination(
    project_id: str,
    elim_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_project_for_write(project_id, current_user, db)
    record = db.query(IntercompanyTransaction).filter(
        IntercompanyTransaction.id == elim_id,
        IntercompanyTransaction.project_id == project_id,
    ).first()
    if not record:
        raise HTTPException(404, "Elimination not found")
    db.delete(record)
    db.commit()
