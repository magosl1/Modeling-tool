"""FX rate routes — Block 3: Multi-Currency."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel
from decimal import Decimal
import uuid

from app.db.base import get_db
from app.models.user import User
from app.models.project import FXRate, Project
from app.api.deps import get_current_user, get_project_or_404

router = APIRouter(prefix="/projects", tags=["fx"])


class FXRateRow(BaseModel):
    year: int
    fx_rate: float


class FXConfigIn(BaseModel):
    reporting_currency: str
    fx_source_currency: str
    rates: List[FXRateRow]


@router.get("/{project_id}/fx")
def get_fx_config(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = get_project_or_404(project_id, current_user, db)
    rates = db.query(FXRate).filter(FXRate.project_id == project_id).order_by(FXRate.year).all()
    return {
        "reporting_currency": getattr(project, "reporting_currency", project.currency),
        "fx_source_currency": getattr(project, "fx_source_currency", None),
        "rates": [{"year": r.year, "fx_rate": float(r.fx_rate)} for r in rates],
    }


@router.put("/{project_id}/fx")
def save_fx_config(
    project_id: str,
    body: FXConfigIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = get_project_or_404(project_id, current_user, db)

    # Update project-level currency fields if they exist
    if hasattr(project, "reporting_currency"):
        project.reporting_currency = body.reporting_currency
    if hasattr(project, "fx_source_currency"):
        project.fx_source_currency = body.fx_source_currency

    # Replace all FX rates
    db.query(FXRate).filter(FXRate.project_id == project_id).delete()
    for row in body.rates:
        db.add(FXRate(
            id=str(uuid.uuid4()),
            project_id=project_id,
            year=row.year,
            fx_rate=Decimal(str(row.fx_rate)),
        ))
    db.commit()
    return {"message": f"{len(body.rates)} FX rates saved"}
