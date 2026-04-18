import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import insert
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user, get_project_or_404
from app.api.routes.entities import get_or_create_default_entity
from app.db.base import get_db
from app.models.project import (
    AssumptionParam,
    HistoricalData,
    NOLBalance,
    Project,
    ProjectedFinancial,
    ProjectionAssumption,
)
from app.models.user import User
from app.services.projection_engine import ProjectionEngine

router = APIRouter(prefix="/projects", tags=["projections"])


# PNL items that users enter as negative values per template convention "(-)".
# The projection engine works with positive magnitudes for all items, so we
# normalise these to abs() when loading from the DB (same treatment as BS/CF).
_PNL_EXPENSE_ITEMS = frozenset({
    "Cost of Goods Sold",
    "SG&A",
    "R&D",
    "D&A",
    "Amortization of Intangibles",
    "Other OpEx",
    "Interest Expense",
    "Tax",
})


def _load_historical(project_id: str, db: Session) -> tuple:
    records = db.query(HistoricalData).filter(HistoricalData.project_id == project_id).all()
    pnl, bs, cf = {}, {}, {}
    years = set()
    for r in records:
        val = Decimal(str(r.value))
        # Engine works with positive magnitudes internally.
        # BS and CF are already abs()'d; PNL expense items follow the same rule.
        if r.statement_type in ("BS", "CF") or r.line_item in _PNL_EXPENSE_ITEMS:
            val = abs(val)

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
    assumptions_db = (
        db.query(ProjectionAssumption)
        .options(joinedload(ProjectionAssumption.params))
        .filter(ProjectionAssumption.project_id == project_id)
        .all()
    )

    # First, collect raw items per module
    raw: Dict[str, list] = {}
    for a in assumptions_db:
        params = [{"param_key": p.param_key, "year": p.year, "value": Decimal(str(p.value))} for p in a.params]
        raw.setdefault(a.module, []).append({
            "line_item": a.line_item,
            "projection_method": a.projection_method,
            "params": params,
        })

    # Transform into the format the ProjectionEngine expects per module
    return _transform_assumptions(raw)


def _transform_assumptions(raw: Dict[str, list]) -> Dict:
    """Convert generic {module: [{line_item, projection_method, params}]} into
    the module-specific dict shapes that ProjectionEngine expects."""
    result: Dict = {}

    # --- Revenue: engine expects {"streams": [{stream_name, projection_method, params}]} ---
    if "revenue" in raw:
        streams = []
        for item in raw["revenue"]:
            streams.append({
                "stream_name": item["line_item"],
                "projection_method": item["projection_method"],
                "params": item["params"],
            })
        result["revenue"] = {"streams": streams}

    # --- COGS: engine reads projection_method + params from top-level dict ---
    if "cogs" in raw and raw["cogs"]:
        item = raw["cogs"][0]  # Single COGS item
        result["cogs"] = {
            "projection_method": item["projection_method"],
            "params": item["params"],
        }

    # --- OpEx: engine expects {"items": [...]} — already correct ---
    if "opex" in raw:
        result["opex"] = {"items": raw["opex"]}

    # --- D&A: engine expects {"depreciation": {method, params}, "amortization": {method, params}} ---
    if "da" in raw:
        da_result: Dict = {}
        for item in raw["da"]:
            li = item["line_item"]
            if "depreciation" in li.lower() or li == "D&A":
                da_result["depreciation"] = {
                    "method": item["projection_method"],
                    "params": item["params"],
                }
            if "amortization" in li.lower():
                da_result["amortization"] = {
                    "method": item["projection_method"],
                    "params": item["params"],
                }
        result["da"] = da_result

    # --- Working Capital: engine expects {inventories: {method, params}, accounts_receivable: ...} ---
    if "working_capital" in raw:
        WC_KEY_MAP = {
            "Inventories": "inventories",
            "Accounts Receivable": "accounts_receivable",
            "Prepaid Expenses & Other Current Assets": "prepaid",
            "Accounts Payable": "accounts_payable",
            "Accrued Liabilities": "accrued_liabilities",
            "Other Current Liabilities": "other_current_liabilities",
        }
        wc_result: Dict = {}
        for item in raw["working_capital"]:
            key = WC_KEY_MAP.get(item["line_item"])
            if key:
                wc_result[key] = {
                    "method": item["projection_method"],
                    "params": item["params"],
                }
        result["working_capital"] = wc_result

    # --- Capex: engine reads projection_method + params from top-level dict ---
    if "capex" in raw and raw["capex"]:
        item = raw["capex"][0]
        result["capex"] = {
            "projection_method": item["projection_method"],
            "params": item["params"],
        }

    # --- Debt: engine expects {interest_rate: {method, rate params}, repayment params, ...} ---
    if "debt" in raw and raw["debt"]:
        item = raw["debt"][0]
        method = item["projection_method"]
        # Build a flat dict with all params accessible + the method
        debt_result: Dict = {
            "projection_method": method,
            "params": item["params"],
            "interest_rate": {"method": "fixed", "params": []},
        }
        # Extract interest rate params if present
        for p in item["params"]:
            if p["param_key"] == "interest_rate":
                debt_result["interest_rate"] = {
                    "method": "fixed",
                    "params": [{"param_key": "rate", "year": p["year"], "value": p["value"]}],
                }
        result["debt"] = debt_result

    # --- Tax: engine reads projection_method + params from top-level dict ---
    if "tax" in raw and raw["tax"]:
        item = raw["tax"][0]
        result["tax"] = {
            "projection_method": item["projection_method"],
            "params": item["params"],
        }

    # --- Dividends: engine reads projection_method + params from top-level dict ---
    if "dividends" in raw and raw["dividends"]:
        item = raw["dividends"][0]
        result["dividends"] = {
            "projection_method": item["projection_method"],
            "params": item["params"],
        }

    # --- Interest Income: engine reads projection_method + params from top-level dict ---
    if "interest_income" in raw and raw["interest_income"]:
        item = raw["interest_income"][0]
        result["interest_income"] = {
            "projection_method": item["projection_method"],
            "params": item["params"],
        }

    # --- Non-Operating: engine expects {non_operating_assets: {method}, other_nonop_pl: {method}, equity: {method}} ---
    if "non_operating" in raw:
        nonop_result: Dict = {}
        for item in raw["non_operating"]:
            li = item["line_item"]
            if "non-operating assets" in li.lower() or "non_operating_assets" in li.lower():
                nonop_result["non_operating_assets"] = {
                    "method": item["projection_method"],
                    "params": item["params"],
                }
            elif "goodwill" in li.lower():
                nonop_result["goodwill"] = {
                    "method": item["projection_method"],
                    "params": item["params"],
                }
            elif "other non-operating" in li.lower() or "non-operating income" in li.lower():
                nonop_result["other_nonop_pl"] = {
                    "method": item["projection_method"],
                    "params": item["params"],
                }
            elif "equity" in li.lower():
                nonop_result["equity"] = {
                    "method": item["projection_method"],
                    "params": item["params"],
                }
        result["non_operating"] = nonop_result

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
    project = get_project_or_404(project_id, current_user, db)
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

    # Ensure an entity exists for this project (backward compat for single-entity projects)
    entity = get_or_create_default_entity(project, db)

    # Store projected financials — bulk insert is significantly faster than
    # individual db.add() calls for potentially hundreds of rows.
    # Scope deletes to this entity so parallel multi-entity runs don't clobber each other.
    db.query(ProjectedFinancial).filter(
        ProjectedFinancial.project_id == project_id,
        ProjectedFinancial.entity_id == entity.id,
        ProjectedFinancial.scenario_id == None,  # noqa: E711
    ).delete()
    db.query(NOLBalance).filter(NOLBalance.project_id == project_id).delete()

    def _rows_for_statement(data: dict, stmt_type: str) -> list:
        rows = []
        for line_item, year_vals in data.items():
            for year, value in year_vals.items():
                rows.append({
                    "id": str(uuid.uuid4()),
                    "project_id": project_id,
                    "entity_id": entity.id,
                    "statement_type": stmt_type,
                    "line_item": line_item,
                    "year": year,
                    "value": value,
                })
        return rows

    all_financial_rows = (
        _rows_for_statement(result.pnl, "PNL")
        + _rows_for_statement(result.bs, "BS")
        + _rows_for_statement(result.cf, "CF")
    )
    if all_financial_rows:
        db.execute(insert(ProjectedFinancial), all_financial_rows)

    nol_rows = [
        {
            "id": str(uuid.uuid4()),
            "project_id": project_id,
            "year": year,
            "nol_opening": nol["nol_opening"],
            "nol_used": nol["nol_used"],
            "nol_closing": nol["nol_closing"],
        }
        for year, nol in result.nol_balances.items()
    ]
    if nol_rows:
        db.execute(insert(NOLBalance), nol_rows)

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
    get_project_or_404(project_id, current_user, db)

    # Include historical data for context
    hist_records = db.query(HistoricalData).filter(HistoricalData.project_id == project_id).all()
    result = {"PNL": {}, "BS": {}, "CF": {}}
    historical_years = set()
    projected_years = set()

    for r in hist_records:
        result[r.statement_type].setdefault(r.line_item, {})[r.year] = str(r.value)
        historical_years.add(r.year)

    # Overlay projected data (projected years take precedence)
    proj_records = db.query(ProjectedFinancial).filter(ProjectedFinancial.project_id == project_id).all()
    for r in proj_records:
        result[r.statement_type].setdefault(r.line_item, {})[r.year] = str(r.value)
        projected_years.add(r.year)

    result["historical_years"] = sorted(historical_years)
    result["projected_years"] = sorted(projected_years)

    return result


@router.get("/{project_id}/projections/export")
def export_projections(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export projected financials to Excel."""
    project = get_project_or_404(project_id, current_user, db)
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

    from io import BytesIO

    import openpyxl
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

    from app.services.template_generator import BS_ITEMS, CF_ITEMS, PNL_ITEMS

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
