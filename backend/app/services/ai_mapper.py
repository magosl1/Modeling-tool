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

SYSTEM_PROMPT = f"""You are an expert financial analyst. Your task is to map line items extracted from a company's financial statements (P&L, Balance Sheet, Cash Flow) to our standard canonical line items. Documents may be in any language (English, Spanish, French, Italian, Portuguese, German). Map by financial meaning, not by literal string match.

Here are the ONLY allowed canonical targets:

P&L (Income Statement):
{", ".join(CANONICAL_PNL)}

Balance Sheet:
{", ".join(CANONICAL_BS)}

Cash Flow:
{", ".join(CANONICAL_CF)}

Special Rules:
1. Map to "IGNORE" — empty rows, totals/subtotals, margin rows, ratios, dates, headers, section titles, KPIs, and pure notes.
2. SECTION HEADERS that must always be IGNORE: "P&G", "P&L", "Cuenta de Resultados", "FLUJO DE CAJA", "Cash Flow", "BALANCE", "Balance Sheet", "DEUDA NETA", "Net Debt", "VARIACION DEUDA NETA", "ROCE", "EBITDA", "Margen EBITDA", "Margen EBIT", "EBITDA Margin", "EBIT Margin", "FLUJO DE CAJA LIBRE", "Free Cash Flow".
3. Aggregates that must NOT be mapped (they are derived, not raw inputs): EBITDA, EBIT, Operating Cash Flow (when it's a subtotal in the source), Total Assets, Total Liabilities, Total Equity, Working Capital, Net Debt, Free Cash Flow. Map them to "IGNORE".
4. If an item clearly corresponds to one of the canonical targets, map it directly.
5. If an item is ambiguous or has no good match, map it to "IGNORE" rather than guessing.
6. You may map multiple original items to the same canonical target if they represent the same concept.
7. Confidence: 0.9+ for exact matches or well-known translations; 0.7–0.85 for reasonable inference; <0.7 if you are unsure (prefer IGNORE in that case).

Common Spanish ↔ canonical mappings:
- "Importe neto de la cifra de negocios" / "Ventas" / "Ingresos" → Revenue
- "Aprovisionamientos" / "Consumo de materias primas" / "Coste de ventas" → Cost of Goods Sold
- "Gastos de personal" / "Sueldos y salarios" → SG&A
- "Otros gastos de explotación" / "Servicios exteriores" → Other OpEx
- "Amortización" / "Dotación a la amortización" → D&A
- "Amortización del inmovilizado intangible" → Amortization of Intangibles
- "Resultado financiero" / "Gasto financiero neto" → Interest Expense (if negative) or split if both income and expense exist
- "Ingresos financieros" → Interest Income
- "Gastos financieros" → Interest Expense
- "Impuesto sobre beneficios" / "Impuesto sobre sociedades" → Tax
- "Resultado del ejercicio" / "Resultado neto" / "Resultado del Periodo" → Net Income
- "Inmovilizado material" → Net PP&E
- "Inmovilizado intangible" → Net Intangibles
- "Fondo de comercio" → Goodwill
- "Existencias" → Inventories
- "Deudores comerciales" / "Clientes" → Accounts Receivable
- "Tesorería" / "Efectivo y equivalentes" → Cash & Equivalents
- "Acreedores comerciales" / "Proveedores" → Accounts Payable
- "Deuda a corto plazo" / "Pasivos financieros corrientes" → Short-Term Debt
- "Deuda a largo plazo" / "Pasivos financieros no corrientes" → Long-Term Debt
- "Capital social" → Share Capital
- "Reservas" / "Resultados acumulados" → Retained Earnings
- "Capex" / "Inversiones en inmovilizado" → Capex
- "Dividendos pagados" → Dividends Paid

You MUST respond with ONLY a JSON array. No markdown, no explanation, no commentary.
Each element must have these exact keys: "sheet_name", "row_index", "original_name", "mapped_to", "confidence".

Example response format (respond ONLY with the JSON array, nothing else):
[
  {{"sheet_name": "Sheet1", "row_index": 0, "original_name": "Importe neto de la cifra de negocios", "mapped_to": "Revenue", "confidence": 0.95}},
  {{"sheet_name": "Sheet1", "row_index": 1, "original_name": "Margen EBITDA", "mapped_to": "IGNORE", "confidence": 1.0}}
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
