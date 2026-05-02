"""AI ingestion service — extracts and normalises financial data from documents.

Key design decisions:
- No response_format schema (breaks Gemini structured output API)
- Minimal prompt: only send label+values rows, skip blanks and header noise
- Plain-text JSON output that any LLM can produce reliably
"""
import csv
import io
import json
import re
from typing import Dict, List, Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.services.document_extractor import ExtractedDocument
from app.services.llm_client import extract_content, smart_complete

log = get_logger("app.services.ai_ingestion")


# ---------------------------------------------------------------------------
# Output schema (validation only — NOT sent as JSON schema to the LLM)
# ---------------------------------------------------------------------------

class ExtractedFinancialItem(BaseModel):
    standard_metric: str
    original_name: str
    values: Dict[str, float]  # {period: amount}


class LLMFinancialExtraction(BaseModel):
    currency: Optional[str] = None
    scale: Optional[str] = None
    periods: List[str]
    financial_data: List[ExtractedFinancialItem]
    unmapped_items: List[str]


# ---------------------------------------------------------------------------
# Allowed metrics catalogue (compact form for the prompt)
# ---------------------------------------------------------------------------

_PNL = "Revenue,Cost of Goods Sold,Gross Profit,SG&A,R&D,D&A,Other OpEx,EBIT,Interest Income,Interest Expense,EBT,Tax,Net Income"
_BS  = "Cash & Equivalents,Accounts Receivable,Inventories,Prepaid Expenses & Other Current Assets,Net PP&E,PP&E Gross,Accumulated Depreciation,Goodwill,Net Intangibles,Accounts Payable,Short-Term Debt,Long-Term Debt,Share Capital,Retained Earnings,Other Equity (AOCI, Treasury Stock, etc.)"
_CF  = "Operating Cash Flow,Capex,Investing Cash Flow,Debt Issuance / Repayment,Dividends Paid,Financing Cash Flow,Net Change in Cash,D&A Add-back,Changes in Working Capital"

SYSTEM_PROMPT = f"""\
You are a financial data extraction engine. Extract financial statement data from the CSV below and return ONLY a valid JSON object — no markdown, no explanation.

JSON format:
{{"currency":"EUR","scale":"millions","periods":["2021","2022","2023"],"financial_data":[{{"standard_metric":"Revenue","original_name":"Total Revenues","values":{{"2021":100.0,"2022":120.0,"2023":135.0}}}},{{"standard_metric":"Net Income","original_name":"Beneficio Neto","values":{{"2021":10.0,"2022":12.0,"2023":15.0}}}}],"unmapped_items":[]}}

Rules:
1. Detect period headers (years, quarters, LTM) as keys in "values". All must appear in "periods".
2. Map each row label to ONE of these allowed metrics (English or Spanish labels, fuzzy match):
   PNL: {_PNL}
   BS: {_BS}
   CF: {_CF}
3. Values must be floats. Negatives in parentheses like (100) become -100.0. Missing = 0.0.
4. Unmapped rows go to "unmapped_items" as strings.
5. Return ONLY the JSON object. No other text.
"""


# ---------------------------------------------------------------------------
# Document → compact CSV (only rows with a label and at least one number)
# ---------------------------------------------------------------------------

def _looks_numeric(val: str) -> bool:
    """True if val looks like a number (handles parentheses negatives)."""
    v = val.strip().replace(",", "").replace("(", "-").replace(")", "")
    try:
        float(v)
        return True
    except ValueError:
        return False


def document_to_compact_csv(doc: ExtractedDocument, max_rows: int = 150) -> str:
    """Build a minimal CSV: only rows that have a text label AND at least one numeric value.
    
    This dramatically reduces token count compared to sending the raw sheet and
    avoids Gemini's content filter triggering on large financial dumps.
    """
    output = io.StringIO()
    writer = csv.writer(output)
    total = 0

    for sheet in doc.sheets:
        writer.writerow([f"--- {sheet.name} ---"])
        for row in sheet.rows:
            if total >= max_rows:
                break
            cells = [str(x).strip() if x is not None else "" for x in row]
            if not cells:
                continue
            # Must have a non-empty first cell (the label) and ≥1 numeric cell
            label = cells[0]
            rest = cells[1:]
            if not label or not any(_looks_numeric(c) for c in rest if c):
                continue
            writer.writerow(cells)
            total += 1

    return output.getvalue()


def _clean_json(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Main extraction
# ---------------------------------------------------------------------------

def run_ai_extraction(
    user_id: str,
    extracted_doc: ExtractedDocument,
    db: Session,
) -> LLMFinancialExtraction:
    """Call the LLM and return a validated LLMFinancialExtraction."""
    csv_text = document_to_compact_csv(extracted_doc)
    char_count = len(csv_text)
    log.info("ai_ingestion_csv_built", chars=char_count, rows_approx=csv_text.count("\n"))

    # If somehow still huge, hard-truncate at 12k chars (~3k tokens)
    if char_count > 12000:
        csv_text = csv_text[:12000] + "\n... (truncated)"

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Financial data CSV:\n\n{csv_text}"},
    ]

    res = smart_complete(
        user_id=user_id,
        db=db,
        messages=messages,
        max_tokens=4096,
    )

    content_str = extract_content(res)
    log.info("ai_ingestion_response", chars=len(content_str), preview=content_str[:300])

    if not content_str or not content_str.strip():
        raise ValueError(
            "AI model returned an empty response. "
            "This may be a Gemini content filter issue — try again or check your model settings."
        )

    cleaned = _clean_json(content_str)

    # Primary parse
    try:
        data_dict = json.loads(cleaned)
    except json.JSONDecodeError as e:
        # Fallback: extract first {...} block
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            try:
                data_dict = json.loads(match.group())
            except json.JSONDecodeError:
                log.error("ai_ingestion_json_parse_failed", content=content_str[:500])
                raise ValueError(f"AI returned invalid JSON: {e}")
        else:
            log.error("ai_ingestion_no_json_found", content=content_str[:500])
            raise ValueError(f"AI returned no JSON. Response preview: {content_str[:200]}")

    try:
        return LLMFinancialExtraction(**data_dict)
    except Exception as e:
        log.error("ai_ingestion_schema_error", error=str(e), data=str(data_dict)[:300])
        raise ValueError(f"AI JSON schema mismatch: {e}")
