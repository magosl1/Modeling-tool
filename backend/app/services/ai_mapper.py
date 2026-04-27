"""AI Mapper — maps extracted document rows to canonical financial items.

Uses plain JSON responses instead of tool calls for maximum provider compatibility.
Never touches or sees the actual numbers, only the text labels.
"""
from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.services.document_extractor import ExtractedDocument
from app.services.llm_client import cheap_complete, smart_complete, extract_content
from app.services.template_generator import BS_ITEMS, CF_ITEMS, PNL_ITEMS

log = get_logger("app.ai_mapper")


# Flatten the tuples into just the names for the prompt
CANONICAL_PNL = [item[0] if isinstance(item, tuple) else item for item in PNL_ITEMS]
CANONICAL_BS = [item[0] if isinstance(item, tuple) else item for item in BS_ITEMS]
CANONICAL_CF = [item[0] if isinstance(item, tuple) else item for item in CF_ITEMS]

SYSTEM_PROMPT = f"""You are an expert financial analyst. Your task is to map line items extracted from a company's financial statements (P&L, Balance Sheet, Cash Flow) to our standard canonical line items.

Here are the ONLY allowed canonical targets:

P&L (Income Statement):
{", ".join(CANONICAL_PNL)}

Balance Sheet:
{", ".join(CANONICAL_BS)}

Cash Flow:
{", ".join(CANONICAL_CF)}

Special Rules:
1. Ignore empty rows, totals, subtotals, dates, headers, or pure notes. For these, map them to "IGNORE".
2. If an item clearly corresponds to one of the canonical targets, map it directly.
3. If an item does not fit nicely, or is ambiguous, map it to "IGNORE".
4. You may map multiple original items to the same canonical target if they represent the same concept.
5. Base your decision primarily on the 'original_name'.
6. Evaluate the confidence of your mapping (0.0 to 1.0). Be highly confident (0.9+) for exact matches or common translations (e.g., "Ventas" -> "Revenue"), and less confident (<0.8) for vague items.

You MUST respond with ONLY a JSON array. No markdown, no explanation, no commentary.
Each element must have these exact keys: "sheet_name", "row_index", "original_name", "mapped_to", "confidence".

Example response format (respond ONLY with the JSON array, nothing else):
[
  {{"sheet_name": "Sheet1", "row_index": 0, "original_name": "Ventas", "mapped_to": "Revenue", "confidence": 0.95}},
  {{"sheet_name": "Sheet1", "row_index": 1, "original_name": "Total", "mapped_to": "IGNORE", "confidence": 1.0}}
]
"""


def _extract_labels(doc: ExtractedDocument) -> list[dict[str, Any]]:
    """Extract just the text labels (typically first column) from the document."""
    labels = []
    for sheet in doc.sheets:
        for r_idx, row in enumerate(sheet.rows):
            # Find the first non-null string in the row to use as label
            label = ""
            for cell in row:
                if isinstance(cell, str) and cell.strip():
                    label = cell.strip()
                    break
            
            # Only include rows that actually have a label
            if label:
                labels.append({
                    "sheet_name": sheet.name,
                    "row_index": r_idx,
                    "original_name": label
                })
    return labels


def _parse_json_from_text(text: str) -> list[dict[str, Any]]:
    """Robustly extract a JSON array from LLM text output.
    
    Handles cases where the model wraps JSON in markdown code blocks,
    adds commentary, or other formatting quirks.
    """
    if not text or not text.strip():
        return []
    
    text = text.strip()
    
    # Try direct parse first
    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result
        if isinstance(result, dict) and "mappings" in result:
            return result["mappings"]
    except json.JSONDecodeError:
        pass
    
    # Try to extract JSON from markdown code blocks
    code_block_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if code_block_match:
        try:
            result = json.loads(code_block_match.group(1).strip())
            if isinstance(result, list):
                return result
            if isinstance(result, dict) and "mappings" in result:
                return result["mappings"]
        except json.JSONDecodeError:
            pass
    
    # Try to find the first [ ... ] block in the text
    bracket_match = re.search(r'\[.*\]', text, re.DOTALL)
    if bracket_match:
        try:
            result = json.loads(bracket_match.group(0))
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass
    
    return []


def map_document_phase1(user_id: str, db: Session, doc: ExtractedDocument) -> list[dict[str, Any]]:
    """Run Phase 1 mapping on an extracted document."""
    labels = _extract_labels(doc)
    
    if not labels:
        return []

    # Format the input for the LLM
    items_text = json.dumps(labels, indent=2, ensure_ascii=False)
    
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Map the following line items. Respond with ONLY a JSON array:\n{items_text}"}
    ]

    log.info("phase1_mapper_start", user_id=user_id, item_count=len(labels))

    response = cheap_complete(
        user_id=user_id,
        db=db,
        messages=messages,
        max_tokens=4096,
    )

    text = extract_content(response)
    mappings = _parse_json_from_text(text)
    
    if mappings:
        log.info("phase1_mapper_success", user_id=user_id, mapped_count=len(mappings))
    else:
        log.warning("phase1_mapper_no_json", user_id=user_id, response_preview=text[:200] if text else "empty")
    
    return mappings


def map_document_phase2(user_id: str, db: Session, doc: ExtractedDocument, phase1_mappings: list[dict[str, Any]] = None) -> list[dict[str, Any]]:
    """Run Phase 2 mapping on an extracted document using the smart model.
    
    This is used for complex documents that failed Phase 1 validation or heuristics.
    """
    labels = _extract_labels(doc)
    
    if not labels:
        return []

    items_text = json.dumps(labels, indent=2, ensure_ascii=False)
    
    # We can pass the phase 1 mappings as context to help the smart model
    context = ""
    if phase1_mappings:
        context = f"The previous cheaper model attempted this mapping but struggled. Here was its attempt:\n{json.dumps(phase1_mappings, indent=2)}\n\nPlease provide a fully corrected mapping.\n\n"

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"{context}Map the following line items. Respond with ONLY a JSON array:\n{items_text}"}
    ]

    log.info("phase2_mapper_start", user_id=user_id, item_count=len(labels))

    response = smart_complete(
        user_id=user_id,
        db=db,
        messages=messages,
        max_tokens=8192,
    )

    text = extract_content(response)
    mappings = _parse_json_from_text(text)
    
    if mappings:
        log.info("phase2_mapper_success", user_id=user_id, mapped_count=len(mappings))
    else:
        log.warning("phase2_mapper_no_json", user_id=user_id, response_preview=text[:200] if text else "empty")
    
    return mappings
