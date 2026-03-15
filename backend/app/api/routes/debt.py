"""Revolver / Cash Sweep configuration routes — Block 2."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from decimal import Decimal
import uuid

from app.db.base import get_db
from app.models.user import User
from app.models.project import RevolverConfig, DebtTranche
from app.api.deps import get_current_user, get_project_or_404

router = APIRouter(prefix="/projects", tags=["debt"])


class RevolverConfigIn(BaseModel):
    revolver_limit: float = 0.0
    revolver_rate: float = 0.0
    minimum_cash_balance: float = 0.0
    scenario_id: Optional[str] = None


class DebtTrancheIn(BaseModel):
    id: Optional[str] = None
    name: str
    principal: float
    rate: float
    maturity_year: int
    amortization_method: str = "bullet"
    display_order: int = 0


@router.get("/{project_id}/debt/revolver")
def get_revolver_config(
    project_id: str,
    scenario_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_project_or_404(project_id, current_user, db)
    config = db.query(RevolverConfig).filter(
        RevolverConfig.project_id == project_id,
        RevolverConfig.scenario_id == scenario_id,
    ).first()
    if not config:
        return {"revolver_limit": 0, "revolver_rate": 0, "minimum_cash_balance": 0}
    return {
        "revolver_limit": float(config.revolver_limit),
        "revolver_rate": float(config.revolver_rate),
        "minimum_cash_balance": float(config.minimum_cash_balance),
    }


@router.put("/{project_id}/debt/revolver")
def save_revolver_config(
    project_id: str,
    body: RevolverConfigIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_project_or_404(project_id, current_user, db)
    config = db.query(RevolverConfig).filter(
        RevolverConfig.project_id == project_id,
        RevolverConfig.scenario_id == body.scenario_id,
    ).first()
    if config:
        config.revolver_limit = Decimal(str(body.revolver_limit))
        config.revolver_rate = Decimal(str(body.revolver_rate))
        config.minimum_cash_balance = Decimal(str(body.minimum_cash_balance))
    else:
        config = RevolverConfig(
            id=str(uuid.uuid4()),
            project_id=project_id,
            scenario_id=body.scenario_id,
            revolver_limit=Decimal(str(body.revolver_limit)),
            revolver_rate=Decimal(str(body.revolver_rate)),
            minimum_cash_balance=Decimal(str(body.minimum_cash_balance)),
        )
        db.add(config)
    db.commit()
    return {"message": "Revolver config saved"}


@router.get("/{project_id}/debt/tranches")
def get_tranches(
    project_id: str,
    scenario_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_project_or_404(project_id, current_user, db)
    tranches = db.query(DebtTranche).filter(
        DebtTranche.project_id == project_id,
        DebtTranche.scenario_id == scenario_id,
    ).order_by(DebtTranche.display_order).all()
    return [
        {
            "id": t.id,
            "name": t.name,
            "principal": float(t.principal),
            "rate": float(t.rate),
            "maturity_year": t.maturity_year,
            "amortization_method": t.amortization_method,
            "display_order": t.display_order,
        }
        for t in tranches
    ]


@router.put("/{project_id}/debt/tranches")
def save_tranches(
    project_id: str,
    body: List[DebtTrancheIn],
    scenario_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Replace all tranches for a project/scenario."""
    get_project_or_404(project_id, current_user, db)
    db.query(DebtTranche).filter(
        DebtTranche.project_id == project_id,
        DebtTranche.scenario_id == scenario_id,
    ).delete()
    for i, t in enumerate(body):
        db.add(DebtTranche(
            id=str(uuid.uuid4()),
            project_id=project_id,
            scenario_id=scenario_id,
            name=t.name,
            principal=Decimal(str(t.principal)),
            rate=Decimal(str(t.rate)),
            maturity_year=t.maturity_year,
            amortization_method=t.amortization_method,
            display_order=i,
        ))
    db.commit()
    return {"message": f"{len(body)} tranches saved"}
