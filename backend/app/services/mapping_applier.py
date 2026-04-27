"""Mapping Applier — Deterministic number extraction based on AI mappings.

Takes the chosen mappings (from Phase 1 or 2) and the raw ExtractedDocument,
and outputs the canonical JSON structure ready to be validated.
"""
from __future__ import annotations

import re
from typing import Any

from app.core.logging import get_logger
from app.services.document_extractor import ExtractedDocument
from app.services.template_generator import BS_ITEMS, CF_ITEMS, PNL_ITEMS

log = get_logger("app.mapping_applier")

# Flatten canonical lists
CANONICAL_PNL = {item[0] if isinstance(item, tuple) else item for item in PNL_ITEMS}
CANONICAL_BS = {item[0] if isinstance(item, tuple) else item for item in BS_ITEMS}
CANONICAL_CF = {item[0] if isinstance(item, tuple) else item for item in CF_ITEMS}

# Regex to detect years in column headers (e.g. "2023", "FY 2024", "12/31/2022")
YEAR_REGEX = re.compile(r'\b(19|20)\d{2}\b')


def _extract_years(headers: list[Any]) -> dict[int, int]:
    """Find columns that look like years in a header row.
    Returns mapping of {column_index: year}.
    """
    year_cols = {}
    for i, cell in enumerate(headers):
        if not cell:
            continue
        # Convert to string to check for year patterns
        cell_str = str(cell)
        matches = YEAR_REGEX.findall(cell_str)
        if matches:
            # Take the last match as the year (e.g. "FY 2023" -> 2023)
            # findall returns just the captured group '(19|20)' so we use search instead
            match = YEAR_REGEX.search(cell_str)
            if match:
                try:
                    year = int(match.group())
                    # basic sanity check
                    if 1950 <= year <= 2100:
                        year_cols[i] = year
                except ValueError:
                    pass
    return year_cols


def apply_mappings(doc: ExtractedDocument, mappings: list[dict[str, Any]]) -> dict[str, Any]:
    """Apply the mappings to the raw document to extract the numeric values.

    Outputs a canonical structure like:
    {
      "PNL": { "Revenue": {2023: 100.0, 2024: 120.0}, ... },
      "BS": { ... },
      "CF": { ... }
    }
    """
    result: dict[str, dict[str, dict[int, float]]] = {
        "PNL": {},
        "BS": {},
        "CF": {}
    }

    # Group mappings by sheet
    sheet_mappings = {}
    for m in mappings:
        mapped_to = m.get("mapped_to")
        if not mapped_to or mapped_to == "IGNORE":
            continue
            
        sheet = m["sheet_name"]
        if sheet not in sheet_mappings:
            sheet_mappings[sheet] = []
        sheet_mappings[sheet].append(m)

    log.info("applying_mappings", sheets=list(sheet_mappings.keys()))

    for sheet_data in doc.sheets:
        if sheet_data.name not in sheet_mappings:
            continue
            
        sm = sheet_mappings[sheet_data.name]
        
        # 1. Identify year columns
        year_cols = {}
        for row_idx in range(min(5, sheet_data.row_count)):
            row = sheet_data.rows[row_idx]
            found = _extract_years(row)
            if found:
                if len(found) > len(year_cols):
                    year_cols = found
                    
        if not year_cols:
            log.warning("no_years_found", sheet=sheet_data.name)
            continue

        # 2. Extract mapped values
        for m in sm:
            row_idx = m["row_index"]
            mapped_to = m["mapped_to"]
            
            stmt = None
            if mapped_to in CANONICAL_PNL:
                stmt = "PNL"
            elif mapped_to in CANONICAL_BS:
                stmt = "BS"
            elif mapped_to in CANONICAL_CF:
                stmt = "CF"
                
            if not stmt:
                continue

            if row_idx >= sheet_data.row_count:
                continue
            row = sheet_data.rows[row_idx]
            
            if mapped_to not in result[stmt]:
                result[stmt][mapped_to] = {}
            
            for col_idx, year in year_cols.items():
                if col_idx < len(row):
                    val = row[col_idx]
                    
                    if val is not None:
                        try:
                            if isinstance(val, str):
                                val = val.replace(",", "").replace(" ", "").replace("€", "").replace("$", "")
                                if val.startswith("(") and val.endswith(")"):
                                    val = "-" + val[1:-1]
                            f_val = float(val)
                            
                            if year in result[stmt][mapped_to]:
                                result[stmt][mapped_to][year] += f_val
                            else:
                                result[stmt][mapped_to][year] = f_val
                                
                        except (ValueError, TypeError):
                            pass

    return result
