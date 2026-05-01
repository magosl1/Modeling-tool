import os
import shutil
import uuid
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_project_for_write, get_project_or_404
from app.api.routes.revenue_streams import _sync_revenue_assumptions
from app.core.logging import get_logger
from app.core.rate_limit import limiter
from app.db.base import get_db
from app.models.project import HistoricalData, Project, RevenueStream, UploadedFile
from app.models.user import User
from app.services.ai_ingestion_service import run_ai_extraction
from app.services.ai_mapper import map_document_phase1, map_document_phase2
from app.services.complexity_detector import evaluate_complexity
from app.services.document_extractor import extract_document
from app.services.historical_validator import (
    parse_historical_excel,
    validate_historical_data,
)
from app.services.mapping_applier import apply_mappings
from app.services.template_generator import (
    BS_ITEMS,
    CF_ITEMS,
    PNL_ITEMS,
    generate_historical_template,
)

router = APIRouter(prefix="/projects", tags=["historical"])
log = get_logger("app.api.historical")

MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_PROJECT_UPLOAD_BYTES = 50 * 1024 * 1024 # 50 MB total limit per project
UPLOAD_DIR = "/app/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

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


@router.post("/{project_id}/documents/batch")
async def upload_documents_batch(
    project_id: str,
    files: List[UploadFile] = File(...),
    entity_id: str | None = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_project_or_404(project_id, current_user, db)
    valid_entity_id = _resolve_entity_for_project(project_id, entity_id, db)
    
    current_size = db.query(func.sum(UploadedFile.file_size_bytes)).filter(
        UploadedFile.project_id == project_id
    ).scalar() or 0

    new_files = []
    for f in files:
        file_bytes = await f.read()
        size = len(file_bytes)
        
        if current_size + size > MAX_PROJECT_UPLOAD_BYTES:
            raise HTTPException(400, "Project upload limit (50MB) exceeded.")
            
        current_size += size
        
        file_id = str(uuid.uuid4())
        ext = os.path.splitext(f.filename)[1] if f.filename else ".txt"
        local_path = os.path.join(UPLOAD_DIR, f"{file_id}{ext}")
        
        with open(local_path, "wb") as out:
            out.write(file_bytes)
            
        doc = UploadedFile(
            id=file_id,
            project_id=project_id,
            entity_id=valid_entity_id,
            file_type="historical",
            file_path=local_path,
            original_filename=f.filename or "unknown",
            file_size_bytes=size,
            upload_status="pending",
            is_ignored=False,
        )
        db.add(doc)
        new_files.append(doc)
        
    db.commit()
    for d in new_files:
        db.refresh(d)
        
    return [{"id": d.id, "filename": d.original_filename, "size": d.file_size_bytes} for d in new_files]


@router.get("/{project_id}/documents")
def list_documents(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_project_or_404(project_id, current_user, db)
    docs = db.query(UploadedFile).filter(
        UploadedFile.project_id == project_id,
        UploadedFile.file_type == "historical"
    ).order_by(UploadedFile.uploaded_at.desc()).all()
    
    return [
        {
            "id": d.id,
            "filename": d.original_filename,
            "size": d.file_size_bytes,
            "status": d.upload_status,
            "is_ignored": d.is_ignored,
            "has_analysis": d.ai_analysis_json is not None,
            "missing_inputs": d.missing_inputs_json,
            "entity_id": d.entity_id,
            "ai_analysis": d.ai_analysis_json,
        }
        for d in docs
    ]


@router.patch("/{project_id}/documents/{doc_id}/toggle")
def toggle_document(
    project_id: str,
    doc_id: str,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_project_or_404(project_id, current_user, db)
    doc = db.query(UploadedFile).filter(UploadedFile.id == doc_id, UploadedFile.project_id == project_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")
        
    is_ignored = payload.get("is_ignored")
    if is_ignored is not None:
        doc.is_ignored = bool(is_ignored)
        db.commit()
    return {"message": "Toggled", "is_ignored": doc.is_ignored}


@router.post("/{project_id}/documents/{doc_id}/analyze")
async def analyze_document(
    project_id: str,
    doc_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_project_or_404(project_id, current_user, db)
    doc = db.query(UploadedFile).filter(UploadedFile.id == doc_id, UploadedFile.project_id == project_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")
        
    if not doc.file_path or not os.path.exists(doc.file_path):
        raise HTTPException(404, "Physical file missing on server")

    with open(doc.file_path, "rb") as f:
        content = f.read()

    try:
        extracted_doc = extract_document(content, doc.original_filename)
    except Exception as e:
        log.warning("ai_ingestion_extraction_failed", error=str(e), file=doc.original_filename)
        raise HTTPException(status_code=400, detail=f"Could not parse file: {str(e)}")

    if not extracted_doc.sheets:
        raise HTTPException(status_code=400, detail="No readable tables or text found in file.")

    try:
        extraction = run_ai_extraction(current_user.id, extracted_doc, db)
    except Exception as e:
        log.error("ai_ingestion_extraction_llm_failed", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"AI extraction failed: {str(e)}")

    parsed = {"PNL": {}, "BS": {}, "CF": {}}
    mappings = []
    
    found_pnl = False
    found_bs = False
    found_cf = False

    for item in extraction.financial_data:
        bucket = "PNL"
        if item.standard_metric in _CANONICAL_PNL:
            bucket = "PNL"
            found_pnl = True
        elif item.standard_metric in _CANONICAL_BS:
            bucket = "BS"
            found_bs = True
        elif item.standard_metric in _CANONICAL_CF:
            bucket = "CF"
            found_cf = True
            
        parsed[bucket][item.standard_metric] = item.values
        mappings.append({
            "original_name": item.original_name,
            "mapped_to": item.standard_metric,
            "confidence": 0.95,
            "sheet_name": "AI_Extracted",
            "row_index": 0
        })
        
    for item in extraction.unmapped_items:
        mappings.append({
            "original_name": item,
            "mapped_to": "IGNORE",
            "confidence": 0.9,
            "sheet_name": "AI_Extracted",
            "row_index": 0
        })

    missing = []
    if not found_pnl: missing.append("PNL (Income Statement)")
    if not found_bs: missing.append("Balance Sheet")
    if not found_cf: missing.append("Cash Flow")

    doc.ai_analysis_json = {
        "parsed": parsed,
        "mappings": mappings,
        "years": extraction.periods,
        "validation_errors": [],
        "ai_stats": {
            "phase2_used": False,
            "reasons": ["Using Structured Outputs end-to-end"],
            "stats": {"currency": extraction.currency, "scale": extraction.scale, "unmapped_count": len(extraction.unmapped_items)}
        }
    }
    doc.missing_inputs_json = missing
    doc.upload_status = "validated"
    db.commit()

    return {
        "message": "Analysis complete",
        "ai_analysis": doc.ai_analysis_json,
        "missing_inputs": doc.missing_inputs_json
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

    # Save to user mapping memory
    mappings = payload.get("mappings", [])
    if mappings:
        from app.models.user_mapping_memory import UserMappingMemory
        for m in mappings:
            orig = m.get("original_name")
            targ = m.get("mapped_to")
            conf = m.get("confidence", 1.0)
            if not orig or not targ or targ == "IGNORE":
                continue
            
            existing = db.query(UserMappingMemory).filter(
                UserMappingMemory.user_id == current_user.id,
                UserMappingMemory.original_name == orig
            ).first()
            
            if existing:
                existing.mapped_to = targ
                existing.confidence = conf
                existing.last_used_at = datetime.now(timezone.utc)
            else:
                db.add(UserMappingMemory(
                    user_id=current_user.id,
                    original_name=orig,
                    mapped_to=targ,
                    confidence=conf,
                ))

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
