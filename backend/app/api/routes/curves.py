from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.base import get_db
from app.models.user import User
from app.models.project import ExternalCurveValue
from app.api.deps import get_current_user, get_project_or_404
import uuid

router = APIRouter(prefix="/projects", tags=["curves"])

@router.get("/{project_id}/curves")
def get_curves(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    get_project_or_404(project_id, current_user, db)
    records = db.query(ExternalCurveValue).filter(ExternalCurveValue.project_id == project_id).all()
    
    result = {}
    for r in records:
        if r.curve_name not in result:
            result[r.curve_name] = {"is_percentage": r.is_percentage, "values": {}}
        result[r.curve_name]["values"][r.year] = float(r.value)
        
    return result

@router.put("/{project_id}/curves")
def save_curves(
    project_id: str,
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    get_project_or_404(project_id, current_user, db)
    
    # Clear existing
    db.query(ExternalCurveValue).filter(ExternalCurveValue.project_id == project_id).delete()
    
    # Save new
    for curve_name, curve_data in data.items():
        is_pct = curve_data.get("is_percentage", False)
        for year_str, val in curve_data.get("values", {}).items():
            db.add(ExternalCurveValue(
                id=str(uuid.uuid4()),
                project_id=project_id,
                curve_name=curve_name,
                is_percentage=is_pct,
                year=int(year_str),
                value=str(val)
            ))
            
    db.commit()
    return {"message": "Curves saved successfully"}
