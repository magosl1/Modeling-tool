from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import Response
from sqlalchemy.orm import Session
from typing import Dict, List
from decimal import Decimal
from app.db.base import get_db
from app.models.user import User
from app.models.project import (
    Project, HistoricalData, ProjectionAssumption, AssumptionParam,
    ProjectedFinancial, NOLBalance
)
from app.api.deps import get_current_user
from app.services.projection_engine import ProjectionEngine
import uuid
from datetime import datetime, timezone

router = APIRouter(prefix="/projects", tags=["projections"])


def _get_project(project_id: str, user: User, db: Session) -> Project:
    p = db.query(Project).filter(Project.id == project_id, Project.user_id == user.id).first()
    if not p:
        raise HTTPException(404, "Project not found")
    return p


def _load_historical(project_id: str, db: Session) -> tuple:
    records = db.query(HistoricalData).filter(HistoricalData.project_id == project_id).all()
    pnl, bs, cf = {}, {}, {}
    years = set()
    for r in records:
        val = Decimal(str(r.value))
        if r.statement_type == "BS" or r.statement_type == "CF":
            val = abs(val) # Engine works with positive values for BS/CF items internally

        year = r.year
        years.add(year)
        if r.statement_type == "PNL":
            pnl.setdefault(r.line_item, {})[year] = val
        elif r.statement_type == "BS":
            bs.setdefault(r.line_item, {})[year] = val
        elif r.statement_type == "CF":
            cf.setdefault(r.line_item, {})[year] = val
    return pnl, bs, cf, sorted(years)


def _load_assumptions(project_id: str, db: Session) -> Dict:
    assumptions_db = db.query(ProjectionAssumption).filter(
        ProjectionAssumption.project_id == project_id
    ).all()

    result = {}
    for a in assumptions_db:
        params_db = db.query(AssumptionParam).filter(AssumptionParam.assumption_id == a.id).all()
        params = [{"param_key": p.param_key, "year": p.year, "value": Decimal(str(p.value))} for p in params_db]

        if a.module not in result:
            result[a.module] = {"items": []}
        result[a.module]["items"].append({
            "line_item": a.line_item,
            "projection_method": a.projection_method,
            "params": params,
        })
    return result


def _run_projection_engine(project: Project, pnl: dict, bs: dict, cf: dict,
                            hist_years: list, assumptions: dict):
    last_hist_year = hist_years[-1] if hist_years else 2023
    proj_years = list(range(last_hist_year + 1, last_hist_year + 1 + project.projection_years))

    engine = ProjectionEngine(
        historical_pnl=pnl,
        historical_bs=bs,
        historical_cf=cf,
        historical_years=hist_years,
        projection_years=proj_years,
        assumptions=assumptions,
    )
    return engine.run(), proj_years


@router.post("/{project_id}/run")
def run_projection(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = _get_project(project_id, current_user, db)
    pnl, bs, cf, hist_years = _load_historical(project_id, db)

    if not hist_years:
        raise HTTPException(400, "No historical data uploaded. Please upload historical data first.")

    assumptions = _load_assumptions(project_id, db)
    result, proj_years = _run_projection_engine(project, pnl, bs, cf, hist_years, assumptions)

    if result.errors:
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "PROJECTION_ERROR",
                    "message": "Projection engine encountered errors",
                    "details": result.errors,
                }
            },
        )

    # Store projected financials
    db.query(ProjectedFinancial).filter(ProjectedFinancial.project_id == project_id).delete()
    db.query(NOLBalance).filter(NOLBalance.project_id == project_id).delete()

    def store_statement(data: dict, stmt_type: str):
        for line_item, year_vals in data.items():
            for year, value in year_vals.items():
                db.add(ProjectedFinancial(
                    id=str(uuid.uuid4()),
                    project_id=project_id,
                    statement_type=stmt_type,
                    line_item=line_item,
                    year=year,
                    value=value,
                ))

    store_statement(result.pnl, "PNL")
    store_statement(result.bs, "BS")
    store_statement(result.cf, "CF")

    for year, nol in result.nol_balances.items():
        db.add(NOLBalance(
            id=str(uuid.uuid4()),
            project_id=project_id,
            year=year,
            nol_opening=nol["nol_opening"],
            nol_used=nol["nol_used"],
            nol_closing=nol["nol_closing"],
        ))

    project.status = "projected"
    project.updated_at = datetime.now(timezone.utc)
    db.commit()

    return {
        "message": "Projections complete",
        "projection_years": proj_years,
        "warnings": result.warnings,
    }


@router.get("/{project_id}/projections")
def get_projections(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_project(project_id, current_user, db)
    records = db.query(ProjectedFinancial).filter(ProjectedFinancial.project_id == project_id).all()

    result = {"PNL": {}, "BS": {}, "CF": {}}
    for r in records:
        result[r.statement_type].setdefault(r.line_item, {})[r.year] = str(r.value)

    return result


@router.get("/{project_id}/projections/export")
def export_projections(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export projected financials to Excel."""
    project = _get_project(project_id, current_user, db)
    pnl, bs, cf, hist_years = _load_historical(project_id, db)
    proj_records = db.query(ProjectedFinancial).filter(ProjectedFinancial.project_id == project_id).all()

    if not proj_records:
        raise HTTPException(400, "No projections available. Run the projection engine first.")

    # Build projected dicts
    proj_pnl, proj_bs, proj_cf = {}, {}, {}
    proj_years = set()
    for r in proj_records:
        proj_years.add(r.year)
        if r.statement_type == "PNL":
            proj_pnl.setdefault(r.line_item, {})[r.year] = Decimal(str(r.value))
        elif r.statement_type == "BS":
            proj_bs.setdefault(r.line_item, {})[r.year] = Decimal(str(r.value))
        elif r.statement_type == "CF":
            proj_cf.setdefault(r.line_item, {})[r.year] = Decimal(str(r.value))

    proj_years = sorted(proj_years)
    all_years = hist_years + proj_years

    import openpyxl
    from io import BytesIO
    from openpyxl.styles import Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = openpyxl.Workbook()
    PROJ_FILL = PatternFill(start_color="DBEAFE", end_color="DBEAFE", fill_type="solid")

    def write_export_sheet(ws, line_items, hist_data, proj_data):
        headers = ["Line Item"] + [str(y) for y in all_years]
        for col, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=h)
            cell.font = Font(bold=True)
            if col > 1 + len(hist_years):
                cell.fill = PROJ_FILL

        for row_idx, li in enumerate(line_items, 2):
            ws.cell(row=row_idx, column=1, value=li)
            for col_idx, year in enumerate(all_years, 2):
                if year in hist_years:
                    val = hist_data.get(li, {}).get(year)
                else:
                    val = proj_data.get(li, {}).get(year)
                cell = ws.cell(row=row_idx, column=col_idx, value=float(val) if val is not None else None)
                if year in proj_years:
                    cell.fill = PROJ_FILL

        ws.column_dimensions["A"].width = 45
        for i in range(len(all_years)):
            ws.column_dimensions[get_column_letter(2 + i)].width = 14

    from app.services.template_generator import PNL_ITEMS, CF_ITEMS, BS_ITEMS

    ws_pnl = wb.active
    ws_pnl.title = "P&L"
    write_export_sheet(ws_pnl, [item for item, _ in PNL_ITEMS], pnl, proj_pnl)

    ws_bs = wb.create_sheet("Balance Sheet")
    write_export_sheet(ws_bs, [item for item, _, _ in BS_ITEMS], bs, proj_bs)

    ws_cf = wb.create_sheet("Cash Flow")
    write_export_sheet(ws_cf, [item for item, _ in CF_ITEMS], cf, proj_cf)

    buf = BytesIO()
    wb.save(buf)
    return Response(
        content=buf.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={project.name}_projections.xlsx"},
    )
