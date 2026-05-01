"""Mapping Applier — Deterministic number extraction based on AI mappings.

Takes the chosen mappings (from Phase 1 or 2) and the raw ExtractedDocument,
and outputs the canonical JSON structure ready to be validated.
"""
from __future__ import annotations

import re
from typing import Any, Optional

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

# Excel error markers (English + Spanish locale variants)
EXCEL_ERROR_PREFIXES = ("#REF", "#¡REF", "#NAME", "#¿NOMBRE", "#DIV", "#VALUE",
                        "#¡VALOR", "#NUM", "#¡NUM", "#N/A", "#NULL", "#¡NULO")

_THOUSANDS_DOT = re.compile(r'^-?\d{1,3}(\.\d{3})+$')
_THOUSANDS_COMMA = re.compile(r'^-?\d{1,3}(,\d{3})+$')


def parse_numeric(val: Any) -> Optional[float]:
    """Robust numeric parser for international financial spreadsheets.

    Handles:
    - Native int/float passthrough.
    - European decimals: "876,2" -> 876.2; "1.218,3" -> 1218.3.
    - US decimals: "1,218.3" -> 1218.3; "876.2" -> 876.2.
    - Parentheses negatives: "(3,4)" -> -3.4.
    - Currency symbols and percent signs (raw value, NOT divided by 100).
    - Excel error cells (#¡REF!, #DIV/0!, ...) -> None.
    - Dashes / blank-equivalents -> None.
    """
    if val is None:
        return None
    if isinstance(val, bool):
        return None
    if isinstance(val, (int, float)):
        return float(val)

    s = str(val).strip()
    if not s:
        return None

    # Excel error markers
    if s.upper().startswith(EXCEL_ERROR_PREFIXES) or s.startswith("#"):
        return None

    # Common blank-equivalents
    if s.lower() in ("-", "—", "–", "n/a", "na", "nan", "none", "null"):
        return None

    # Strip currency, percent, NBSP, regular spaces
    s = re.sub(r"[€$£¥% \s]", "", s)
    if not s:
        return None

    # Parentheses → negative
    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg = True
        s = s[1:-1]

    # Leading/trailing minus
    if s.startswith("-"):
        neg = not neg
        s = s[1:]
    if s.endswith("-"):
        neg = not neg
        s = s[:-1]

    if not s:
        return None

    has_comma = "," in s
    has_dot = "." in s

    if has_comma and has_dot:
        # Whichever appears LAST is the decimal separator; the other is thousands.
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif has_comma:
        # Pure thousands pattern (e.g. "1,234,567") -> strip commas.
        # Otherwise treat comma as European decimal separator.
        if _THOUSANDS_COMMA.match(s) and s.count(",") >= 1 and (
            len(s.split(",")[-1]) == 3
        ):
            s = s.replace(",", "")
        else:
            s = s.replace(",", ".")
    elif has_dot:
        # Pure thousands pattern with dots (e.g. "1.234.567") -> strip dots.
        # Single dot followed by ≥4 digits is also thousands ("1.234").
        if _THOUSANDS_DOT.match(s):
            s = s.replace(".", "")

    try:
        f = float(s)
    except ValueError:
        return None

    import math
    if math.isnan(f) or math.isinf(f):
        return None

    return -f if neg else f


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
                if col_idx >= len(row):
                    continue
                val = row[col_idx]
                if val is None:
                    continue

                # Skip cells that are themselves a year header — these come from
                # section header rows (e.g. "P&G (Mn€)" / "FLUJO DE CAJA (Mn€)")
                # where the value column contains the year text instead of a number.
                if isinstance(val, str) and YEAR_REGEX.search(val):
                    continue

                f_val = parse_numeric(val)
                if f_val is None:
                    if isinstance(val, str) and val.strip():
                        log.debug(
                            "unparseable_value",
                            sheet=sheet_data.name,
                            row=row_idx,
                            col=col_idx,
                            mapped_to=mapped_to,
                            value=val[:50],
                        )
                    continue

                # Defensive: cells that parse to exactly the year are headers.
                if f_val == float(year) and (
                    isinstance(val, str) or (isinstance(val, (int, float)) and val == year)
                ):
                    # Only skip if it's clearly a header row (no other numeric data
                    # on this row would also equal the year). We treat any cell that
                    # equals the column's year as a header echo.
                    continue

                if year in result[stmt][mapped_to]:
                    result[stmt][mapped_to][year] += f_val
                else:
                    result[stmt][mapped_to][year] = f_val

    return result
