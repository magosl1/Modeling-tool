import uuid
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, Body
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_project_for_write, get_project_or_404
from app.api.routes.revenue_streams import _sync_revenue_assumptions
from app.db.base import get_db
from app.models.project import HistoricalData, Project, RevenueStream
from app.models.user import User
from app.services.historical_validator import (
    parse_historical_excel,
    validate_historical_data,
)
from app.services.template_generator import (
    BS_ITEMS,
    CF_ITEMS,
    PNL_ITEMS,
    generate_historical_template,
)
from app.services.document_extractor import extract_document
from app.services.ai_mapper import map_document_phase1, map_document_phase2
from app.services.complexity_detector import evaluate_complexity
from app.services.mapping_applier import apply_mappings
from app.core.logging import get_logger

router = APIRouter(prefix="/projects", tags=["historical"])
log = get_logger("app.api.historical")

MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB

# Canonical line-item whitelist used to reject mass-assignment via /save-json.
_CANONICAL_PNL = {item[0] if isinstance(item, tuple) else item for item in PNL_ITEMS}
_CANONICAL_BS = {item[0] if isinstance(item, tuple) else item for item in BS_ITEMS}
_CANONICAL_CF = {item[0] if isinstance(item, tuple) else item for item in CF_ITEMS}


def _resolve_entity_for_project(project_id: str, entity_id: str | None, db: Session) -> str:
    """Return a valid entity_id that belongs to the given project.

    - If entity_id is provided, verify it exists AND belongs to project_id.
      Mismatches are returned as 404 (not 403) to avoid disclosing whether
      the entity exists in another project.
    - If entity_id is None, fall back to the project's default entity.
    """
    from app.models.entity import Entity

    if entity_id:
        entity = (
            db.query(Entity)
            .filter(Entity.id == entity_id, Entity.project_id == project_id)
            .first()
        )
        if not entity:
            raise HTTPException(status_code=404, detail="Entity not found in this project")
        return entity.id

    default_entity = db.query(Entity).filter(Entity.project_id == project_id).first()
    if not default_entity:
        raise HTTPException(status_code=400, detail="No entity found for this project.")
    return default_entity.id


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

    # Fetch configured revenue streams (if any) to customise P&L template
    streams = (
        db.query(RevenueStream)
        .filter(
            RevenueStream.project_id == project_id,
            RevenueStream.scenario_id == None,  # noqa: E711
        )
        .order_by(RevenueStream.display_order)
        .all()
    )
    revenue_lines = [s.stream_name for s in streams] if streams else None

    xlsx = generate_historical_template(years, project.currency, project.scale,
                                        revenue_lines=revenue_lines)
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
    project = get_project_for_write(project_id, current_user, db)
    content = await file.read()

    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(413, f"File too large. Maximum size is {MAX_UPLOAD_SIZE // (1024 * 1024)} MB")

    # Parse
    try:
        parsed, years, detected_sub_lines = parse_historical_excel(content)
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
        
    from app.models.entity import Entity
    default_entity = db.query(Entity).filter(Entity.project_id == project_id).first()
    if not default_entity:
        raise HTTPException(400, "No entity found for this project.")
    entity_id = default_entity.id

    # Store data (delete old first for this entity)
    db.query(HistoricalData).filter(
        HistoricalData.project_id == project_id,
        HistoricalData.entity_id == entity_id
    ).delete()

    sub_line_set = set(detected_sub_lines)

    def store_statement(data: dict, statement_type: str, bucket_map: dict = None):
        for line_item, year_vals in data.items():
            if line_item.startswith("_"):
                continue
            for year, value in year_vals.items():
                bucket = None
                if bucket_map:
                    bucket = bucket_map.get(line_item)
                elif statement_type == "PNL" and line_item in sub_line_set:
                    # Revenue sub-line — tag with bucket so detect endpoint can find them
                    bucket = "Revenue"
                db.add(HistoricalData(
                    id=str(uuid.uuid4()),
                    project_id=project_id,
                    entity_id=entity_id,
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

    # Auto-sync revenue stream definitions when sub-lines were detected
    if detected_sub_lines:
        # Replace existing base-config streams with the detected ones
        db.query(RevenueStream).filter(
            RevenueStream.project_id == project_id,
            RevenueStream.scenario_id == None,  # noqa: E711
        ).delete()
        db.flush()
        for i, name in enumerate(detected_sub_lines):
            db.add(RevenueStream(
                id=str(uuid.uuid4()),
                project_id=project_id,
                scenario_id=None,
                stream_name=name,
                display_order=i,
                projection_method="growth_flat",
            ))
        _sync_revenue_assumptions(project_id, detected_sub_lines, db)

    project.status = "configured" if project.status == "draft" else project.status
    project.updated_at = datetime.now(timezone.utc)
    db.commit()

    return {
        "message": "Historical data uploaded and validated successfully",
        "years": years,
        "detected_revenue_streams": detected_sub_lines,
    }


@router.post("/{project_id}/upload-ai")
async def analyze_historical_ai(
    project_id: str,
    file: UploadFile = File(...),
    entity_id: str | None = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Orchestrator endpoint for AI Ingestion (Paso 8).
    
    1. Extracts tables/text deterministically.
    2. Runs Phase 1 cheap mapping.
    3. Detects complexity.
    4. Runs Phase 2 smart mapping if complex.
    5. Applies mapping to extract numeric arrays.
    
    Returns the mapped canonical structure and any validation errors.
    Does NOT save to DB (wait for human confirmation).
    """
    get_project_or_404(project_id, current_user, db)
    # If a target entity is provided, verify it belongs to this project up front
    # so we don't burn LLM tokens analysing a doc that won't be saveable later.
    if entity_id:
        _resolve_entity_for_project(project_id, entity_id, db)
    content = await file.read()

    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(413, f"File too large. Maximum size is {MAX_UPLOAD_SIZE // (1024 * 1024)} MB")

    import time
    start_time = time.time()
    
    # Step 3: Extractor
    doc = extract_document(content, file.filename)
    
    # Step 4: Mapper Phase 1
    mappings = map_document_phase1(current_user.id, db, doc)
    
    # Step 5: Complexity
    complexity = evaluate_complexity(doc, mappings)
    phase2_used = False
    
    # Step 6: Mapper Phase 2
    if complexity["requires_phase2"]:
        mappings = map_document_phase2(current_user.id, db, doc, phase1_mappings=mappings)
        phase2_used = True
        
    # Step 7: Apply mappings
    parsed = apply_mappings(doc, mappings)
    
    # Extract years
    years_set = set()
    for stmt in parsed.values():
        for line_vals in stmt.values():
            years_set.update(line_vals.keys())
    years = sorted(list(years_set))
    
    # Validate
    errors = validate_historical_data(parsed["PNL"], parsed["BS"], parsed["CF"], years)
    error_list = [
        {"tab": e.tab, "line_item": e.line_item, "year": e.year, "message": e.error_message}
        for e in errors
    ]
    
    latency_ms = int((time.time() - start_time) * 1000)
    log.info(
        "ai_ingestion_complete",
        project_id=project_id,
        user_id=current_user.id,
        file_size=len(content),
        years_found=len(years),
        phase2_used=phase2_used,
        validation_errors=len(errors),
        latency_ms=latency_ms
    )
    
    return {
        "parsed": parsed,
        "mappings": mappings,
        "years": years,
        "validation_errors": error_list,
        "ai_stats": {
            "phase2_used": phase2_used,
            "reasons": complexity["reasons"],
            "stats": complexity["stats"]
        }
    }


@router.post("/{project_id}/save-json")
def save_historical_json(
    project_id: str,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Save the final, validated JSON data from the AI ingestion wizard.
    
    Expected payload format:
    {
      "parsed": {
        "PNL": {"Revenue": {2022: 100, 2023: 150}, ...},
        "BS": {...},
        "CF": {...}
      },
      "years": [2022, 2023]
    }
    """
    project = get_project_for_write(project_id, current_user, db)

    parsed = payload.get("parsed", {})
    if not isinstance(parsed, dict):
        raise HTTPException(400, "Invalid payload: 'parsed' must be an object.")
    entity_id = _resolve_entity_for_project(project_id, payload.get("entity_id"), db)

    # Store data (delete old first for this entity)
    db.query(HistoricalData).filter(
        HistoricalData.project_id == project_id,
        HistoricalData.entity_id == entity_id
    ).delete()

    canonical_by_stmt = {
        "PNL": _CANONICAL_PNL,
        "BS": _CANONICAL_BS,
        "CF": _CANONICAL_CF,
    }

    def store_statement(data: dict, statement_type: str, bucket_map: dict = None):
        canonical = canonical_by_stmt[statement_type]
        for line_item, year_vals in data.items():
            if not isinstance(line_item, str) or line_item.startswith("_"):
                continue
            # Reject anything outside the canonical whitelist for this statement.
            # (Revenue sub-lines bypass this on the legacy /upload route, but the
            # AI pipeline must commit to the canonical contract.)
            if line_item not in canonical:
                log.warning(
                    "save_json_unknown_line_item",
                    statement=statement_type,
                    line_item=line_item[:80],
                    project_id=project_id,
                )
                continue
            if not isinstance(year_vals, dict):
                continue
            for year_str, value in year_vals.items():
                try:
                    year = int(year_str)
                except (TypeError, ValueError):
                    continue
                # Guard against Inf / NaN / non-numeric values that would
                # corrupt downstream calculations.
                try:
                    fval = float(value)
                except (TypeError, ValueError):
                    continue
                import math
                if math.isnan(fval) or math.isinf(fval):
                    continue

                bucket = None
                if bucket_map:
                    bucket = bucket_map.get(line_item)
                db.add(HistoricalData(
                    id=str(uuid.uuid4()),
                    project_id=project_id,
                    entity_id=entity_id,
                    statement_type=statement_type,
                    line_item=line_item,
                    bucket=bucket,
                    year=year,
                    value=fval,
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

    store_statement(parsed.get("PNL", {}), "PNL")
    store_statement(parsed.get("BS", {}), "BS", bs_buckets)
    store_statement(parsed.get("CF", {}), "CF")

    project.status = "configured" if project.status == "draft" else project.status
    project.updated_at = datetime.now(timezone.utc)
    db.commit()

    return {"message": "Historical data saved successfully"}


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
