from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import Response
from sqlalchemy.orm import Session
from typing import List
from app.db.base import get_db
from app.models.user import User
from app.models.project import Project, HistoricalData
from app.api.deps import get_current_user, get_project_or_404
from app.services.template_generator import generate_historical_template
from app.services.historical_validator import parse_historical_excel, validate_historical_data
import uuid
from datetime import datetime, timezone

router = APIRouter(prefix="/projects", tags=["historical"])

MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB


@router.get("/{project_id}/template/historical")
def download_historical_template(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = get_project_or_404(project_id, current_user, db)
    if not project.fiscal_year_end or not project.projection_years:
        raise HTTPException(400, "Configure project (fiscal year end) before downloading template")

    # Build year list from fiscal_year_end going back 3 years as example
    from datetime import date
    fy = project.fiscal_year_end
    years = [fy.year - 2, fy.year - 1, fy.year] if fy else [2021, 2022, 2023]

    xlsx = generate_historical_template(years, project.currency, project.scale)
    return Response(
        content=xlsx,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=historical_template.xlsx"},
    )


@router.post("/{project_id}/upload/historical")
async def upload_historical_data(
    project_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = get_project_or_404(project_id, current_user, db)
    content = await file.read()

    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(413, f"File too large. Maximum size is {MAX_UPLOAD_SIZE // (1024 * 1024)} MB")

    # Parse
    try:
        parsed, years = parse_historical_excel(content)
    except Exception as e:
        raise HTTPException(400, f"Failed to parse Excel file: {str(e)}")

    # Validate
    errors = validate_historical_data(parsed["PNL"], parsed["BS"], parsed["CF"], years)
    if errors:
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "VALIDATION_FAILED",
                    "message": "Historical data validation failed",
                    "details": [
                        {"tab": e.tab, "line_item": e.line_item, "year": e.year, "message": e.error_message}
                        for e in errors
                    ],
                }
            },
        )

    # Store data (delete old first)
    db.query(HistoricalData).filter(HistoricalData.project_id == project_id).delete()

    def store_statement(data: dict, statement_type: str, bucket_map: dict = None):
        for line_item, year_vals in data.items():
            if line_item.startswith("_"):
                continue
            for year, value in year_vals.items():
                bucket = bucket_map.get(line_item) if bucket_map else None
                db.add(HistoricalData(
                    id=str(uuid.uuid4()),
                    project_id=project_id,
                    statement_type=statement_type,
                    line_item=line_item,
                    bucket=bucket,
                    year=year,
                    value=value,
                ))

    bs_buckets = {
        "PP&E Gross": "Fixed Assets", "Accumulated Depreciation": "Fixed Assets",
        "Net PP&E": "Fixed Assets", "Intangibles Gross": "Fixed Assets",
        "Accumulated Amortization": "Fixed Assets", "Net Intangibles": "Fixed Assets",
        "Goodwill": "Fixed Assets",
        "Inventories": "Working Capital", "Accounts Receivable": "Working Capital",
        "Prepaid Expenses & Other Current Assets": "Working Capital",
        "Accounts Payable": "Working Capital", "Accrued Liabilities": "Working Capital",
        "Other Current Liabilities": "Working Capital",
        "Other Long-Term Liabilities": "Other Long-Term",
        "Cash & Equivalents": "Cash",
        "Non-Operating Assets": "Non-Operating",
        "Short-Term Debt": "Debt", "Long-Term Debt": "Debt",
        "Share Capital": "Equity", "Retained Earnings": "Equity",
        "Other Equity (AOCI, Treasury Stock, etc.)": "Equity",
    }

    store_statement(parsed["PNL"], "PNL")
    store_statement(parsed["BS"], "BS", bs_buckets)
    store_statement(parsed["CF"], "CF")

    project.status = "configured" if project.status == "draft" else project.status
    project.updated_at = datetime.now(timezone.utc)
    db.commit()

    return {"message": "Historical data uploaded and validated successfully", "years": years}


@router.get("/{project_id}/historical")
def get_historical_data(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_project_or_404(project_id, current_user, db)
    records = db.query(HistoricalData).filter(HistoricalData.project_id == project_id).all()

    result = {"PNL": {}, "BS": {}, "CF": {}}
    for r in records:
        st = r.statement_type
        result[st].setdefault(r.line_item, {})[r.year] = str(r.value)

    return result
