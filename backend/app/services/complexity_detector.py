"""Complexity detector for AI ingestion.

Evaluates the results of the Phase 1 Mapper and the Document Extractor to
determine if Phase 2 (smart model) is necessary.
"""
from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.services.document_extractor import ExtractedDocument

log = get_logger("app.complexity")

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

CONFIDENCE_THRESHOLD = 0.80
MAPPED_RATIO_THRESHOLD = 0.50  # at least 50% of extracted rows should be mapped (non-IGNORE) to be considered 'good'
MERGED_CELL_RATIO_THRESHOLD = 0.20

CRITICAL_ITEMS = {
    "Revenue",
    "Net Income",
    "Cash & Equivalents",
}


def evaluate_complexity(
    doc: ExtractedDocument,
    phase1_mappings: list[dict[str, Any]]
) -> dict[str, Any]:
    """Decide if the document is complex and requires Phase 2 processing.

    Returns:
        dict with:
          - requires_phase2 (bool)
          - reasons (list[str])
          - stats (dict)
    """
    reasons = []
    
    # 1. Scanned PDF check
    if doc.needs_ocr:
        reasons.append("Document requires OCR (scanned PDF).")
        
    # 2. Merged cell check (messy Excel)
    max_merged_ratio = 0.0
    for sheet in doc.sheets:
        if sheet.merged_cell_ratio > max_merged_ratio:
            max_merged_ratio = sheet.merged_cell_ratio
            
    if max_merged_ratio > MERGED_CELL_RATIO_THRESHOLD:
        reasons.append(f"High ratio of merged header cells ({max_merged_ratio:.1%}).")

    # 3. Mapping stats check
    mapped_count = 0
    low_confidence_count = 0
    mapped_items = set()

    for m in phase1_mappings:
        mapped_to = m.get("mapped_to")
        if mapped_to and mapped_to != "IGNORE":
            mapped_count += 1
            mapped_items.add(mapped_to)
            
            # Check confidence only on actual mapped items
            if m.get("confidence", 0) < CONFIDENCE_THRESHOLD:
                low_confidence_count += 1

    total_rows = sum(s.row_count for s in doc.sheets)
    # We use a heuristic: at least a certain percentage of the document should be mapped.
    # We only count non-empty labels.
    total_labels = len(phase1_mappings)
    
    mapped_ratio = mapped_count / total_labels if total_labels > 0 else 0

    if mapped_ratio < MAPPED_RATIO_THRESHOLD and total_labels > 20: # Only apply if it's a decently sized doc
        reasons.append(f"Low mapping ratio ({mapped_ratio:.1%}).")

    if low_confidence_count > 0:
        # If more than 3 low confidence items, flag it
        if low_confidence_count >= 3:
            reasons.append(f"Found {low_confidence_count} low-confidence mappings.")

    # 4. Critical items check
    missing_critical = []
    for item in CRITICAL_ITEMS:
        if item not in mapped_items:
            missing_critical.append(item)
            
    if missing_critical:
        # Sometimes a sheet might just be a P&L, so it won't have Cash.
        # But if it's missing Revenue AND Cash, it's definitely suspicious.
        # We'll just list it as a reason.
        reasons.append(f"Missing critical line items: {', '.join(missing_critical)}.")

    requires_phase2 = len(reasons) > 0

    stats = {
        "max_merged_ratio": max_merged_ratio,
        "mapped_ratio": mapped_ratio,
        "low_confidence_count": low_confidence_count,
        "missing_critical": missing_critical
    }

    log.info(
        "complexity_evaluated",
        requires_phase2=requires_phase2,
        reasons=reasons,
        stats=stats
    )

    return {
        "requires_phase2": requires_phase2,
        "reasons": reasons,
        "stats": stats
    }
