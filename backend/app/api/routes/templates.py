"""Module-specific template generation and upload routes."""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import Response
from sqlalchemy.orm import Session
from typing import List
from app.db.base import get_db
from app.models.user import User
from app.models.project import Project, ProjectionAssumption
from app.api.deps import get_current_user, get_project_or_404
from app.services.template_generator import generate_module_template
import uuid
from datetime import datetime, timezone

router = APIRouter(prefix="/projects", tags=["templates"])

MODULE_LINE_ITEMS = {
    "revenue": ["Revenue (Total)", "Revenue Stream 1", "Revenue Stream 2"],
    "cogs": ["Cost of Goods Sold"],
    "opex": ["SG&A", "R&D", "Other OpEx"],
    "da": ["D&A", "Amortization of Intangibles"],
    "working_capital": [
        "Inventories", "Accounts Receivable",
        "Prepaid Expenses & Other Current Assets",
        "Accounts Payable", "Accrued Liabilities", "Other Current Liabilities",
    ],
    "capex": ["Maintenance Capex", "Growth Capex"],
    "debt": ["Existing Debt Repayment", "New Debt Issuance", "Interest Rate (%)"],
    "tax": ["Effective Tax Rate (%)"],
    "dividends": ["Dividends Paid"],
    "interest_income": ["Interest Income Yield (%)"],
    "non_operating": ["Non-Operating Assets", "Goodwill", "Other Non-Op Income/(Expense)"],
}


@router.get("/{project_id}/template/{module}")
def download_module_template(
    project_id: str,
    module: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = get_project_or_404(project_id, current_user, db)

    if module not in MODULE_LINE_ITEMS:
        raise HTTPException(400, f"Unknown module: {module}")

    # Get actual line items from configured assumptions (if available)
    assumptions = db.query(ProjectionAssumption).filter(
        ProjectionAssumption.project_id == project_id,
        ProjectionAssumption.module == module,
    ).all()

    if assumptions:
        line_items = [a.line_item for a in assumptions]
    else:
        line_items = MODULE_LINE_ITEMS[module]

    # Year range = last historical year(s)
    from app.models.project import HistoricalData
    hist_years = db.query(HistoricalData.year).filter(
        HistoricalData.project_id == project_id
    ).distinct().order_by(HistoricalData.year).all()
    years = [y[0] for y in hist_years] if hist_years else [2021, 2022, 2023]

    xlsx = generate_module_template(module, line_items, years, project.currency, project.scale)
    return Response(
        content=xlsx,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={module}_template.xlsx"},
    )
