import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_project_or_404
from app.db.base import get_db
from app.models.project import Project, ProjectedFinancial, ValuationInput, ValuationOutput
from app.models.user import User
from app.schemas.project import ValuationInputCreate
from app.services.dcf_engine import DCFEngine

router = APIRouter(prefix="/projects", tags=["valuation"])


def _load_projections(project_id: str, db: Session):
    records = db.query(ProjectedFinancial).filter(ProjectedFinancial.project_id == project_id).all()
    if not records:
        raise HTTPException(400, "No projections found. Run the projection engine first.")
    pnl, bs, cf = {}, {}, {}
    years = set()
    for r in records:
        val = Decimal(str(r.value))
        years.add(r.year)
        if r.statement_type == "PNL":
            pnl.setdefault(r.line_item, {})[r.year] = val
        elif r.statement_type == "BS":
            bs.setdefault(r.line_item, {})[r.year] = val
        elif r.statement_type == "CF":
            cf.setdefault(r.line_item, {})[r.year] = val
    return pnl, bs, cf, sorted(years)


@router.post("/{project_id}/valuation")
def run_valuation(
    project_id: str,
    data: ValuationInputCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = get_project_or_404(project_id, current_user, db)
    pnl, bs, cf, proj_years = _load_projections(project_id, db)

    # Save inputs
    existing = db.query(ValuationInput).filter(ValuationInput.project_id == project_id).first()
    if existing:
        db.delete(existing)

    vi = ValuationInput(
        id=str(uuid.uuid4()),
        project_id=project_id,
        wacc=data.wacc,
        terminal_growth_rate=data.terminal_growth_rate,
        exit_multiple=data.exit_multiple,
        discounting_convention=data.discounting_convention,
        shares_outstanding=data.shares_outstanding,
    )
    db.add(vi)

    # Determine TV method
    tv_method = "exit_multiple" if data.exit_multiple else "gordon_growth"

    engine = DCFEngine(
        pnl=pnl,
        bs=bs,
        cf=cf,
        projection_years=proj_years,
        wacc=Decimal(str(data.wacc)),
        terminal_growth_rate=Decimal(str(data.terminal_growth_rate)),
        exit_multiple=Decimal(str(data.exit_multiple)) if data.exit_multiple else None,
        discounting_convention=data.discounting_convention,
        shares_outstanding=Decimal(str(data.shares_outstanding)) if data.shares_outstanding else None,
        terminal_value_method=tv_method,
    )

    try:
        result = engine.run()
    except ValueError as e:
        raise HTTPException(400, str(e))

    # Save outputs
    existing_out = db.query(ValuationOutput).filter(ValuationOutput.project_id == project_id).first()
    if existing_out:
        db.delete(existing_out)

    vo = ValuationOutput(
        id=str(uuid.uuid4()),
        project_id=project_id,
        enterprise_value=result.enterprise_value,
        net_debt=result.net_debt,
        equity_value=result.equity_value,
        value_per_share=result.value_per_share,
        terminal_value=result.terminal_value,
        pv_fcffs=result.pv_fcffs,
        pv_terminal_value=result.pv_terminal_value,
        method_used=tv_method,
    )
    db.add(vo)

    project.status = "valued"
    project.updated_at = datetime.now(timezone.utc)
    db.commit()

    return {
        "enterprise_value": str(result.enterprise_value),
        "net_debt": str(result.net_debt),
        "equity_value": str(result.equity_value),
        "value_per_share": str(result.value_per_share) if result.value_per_share else None,
        "terminal_value": str(result.terminal_value),
        "pv_fcffs": str(result.pv_fcffs),
        "pv_terminal_value": str(result.pv_terminal_value),
        "method_used": tv_method,
        "fcff_by_year": {str(k): str(v) for k, v in result.fcff_by_year.items()},
        "sensitivity_table": {
            wacc_k: {g_k: str(v) for g_k, v in g_vals.items()}
            for wacc_k, g_vals in result.sensitivity_table.items()
        },
    }


@router.get("/{project_id}/valuation")
def get_valuation(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_project_or_404(project_id, current_user, db)
    vo = db.query(ValuationOutput).filter(ValuationOutput.project_id == project_id).first()
    if not vo:
        raise HTTPException(404, "No valuation found. Run valuation first.")
    return {
        "enterprise_value": str(vo.enterprise_value),
        "net_debt": str(vo.net_debt),
        "equity_value": str(vo.equity_value),
        "value_per_share": str(vo.value_per_share) if vo.value_per_share else None,
        "terminal_value": str(vo.terminal_value),
        "pv_fcffs": str(vo.pv_fcffs),
        "pv_terminal_value": str(vo.pv_terminal_value),
        "method_used": vo.method_used,
    }


@router.get("/{project_id}/valuation/sensitivity")
def get_sensitivity(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Re-compute sensitivity table from stored valuation inputs."""
    get_project_or_404(project_id, current_user, db)
    vi = db.query(ValuationInput).filter(ValuationInput.project_id == project_id).first()
    if not vi:
        raise HTTPException(404, "No valuation inputs found.")

    pnl, bs, cf, proj_years = _load_projections(project_id, db)
    tv_method = "exit_multiple" if vi.exit_multiple else "gordon_growth"

    engine = DCFEngine(
        pnl=pnl, bs=bs, cf=cf, projection_years=proj_years,
        wacc=vi.wacc, terminal_growth_rate=vi.terminal_growth_rate,
        exit_multiple=vi.exit_multiple,
        discounting_convention=vi.discounting_convention,
        shares_outstanding=vi.shares_outstanding,
        terminal_value_method=tv_method,
    )
    result = engine.run()
    return {
        "sensitivity_table": {
            wacc_k: {g_k: str(v) for g_k, v in g_vals.items()}
            for wacc_k, g_vals in result.sensitivity_table.items()
        }
    }
