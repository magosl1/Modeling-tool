"""AI ingestion service — extracts and normalises financial data from documents.

Strategy: plain-text JSON in the system prompt, no response_format schema.
This works identically across Gemini, Claude, and OpenAI and avoids all the
'additionalProperties' / token-limit / structured-output issues we saw before.
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
# Output schema (used only for validation after parsing, NOT sent as JSON schema)
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
# System prompt — explicit JSON example so any LLM understands the format
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are an expert financial analyst and data engineer specialised in extracting \
and normalising financial statements from any format.

## Task
Receive raw CSV/text data exported from Excel and return a single JSON object. \
Do NOT include any explanation, greeting, or markdown — ONLY the JSON object.

## Output format (follow exactly)
{
  "currency": "EUR",
  "scale": "millions",
  "periods": ["2021", "2022", "2023"],
  "financial_data": [
    {
      "standard_metric": "Revenue",
      "original_name": "Total Revenues",
      "values": {"2021": 100.5, "2022": 120.3, "2023": 135.0}
    },
    {
      "standard_metric": "Net Income",
      "original_name": "Beneficio Neto",
      "values": {"2021": 10.2, "2022": 12.5, "2023": 15.1}
    }
  ],
  "unmapped_items": ["Some unrecognised line"]
}

## Rules

### Periods
- Detect all date/period headers (rows or columns): years like "2021", quarters \
like "3Q25", labels like "LTM". Use them as keys in "values".
- "periods" array must contain ALL detected periods in chronological order.

### Mapping to standard metrics
Map every line item to EXACTLY one of these allowed names. Use semantic/fuzzy \
matching across English and Spanish:

PNL: Revenue, Cost of Goods Sold, Gross Profit, SG&A, R&D, D&A, \
Amortization of Intangibles, Other OpEx, EBIT, Interest Income, \
Interest Expense, Other Non-Operating Income / (Expense), EBT, Tax, Net Income

BS: PP&E Gross, Accumulated Depreciation, Net PP&E, Intangibles Gross, \
Accumulated Amortization, Net Intangibles, Goodwill, Inventories, \
Accounts Receivable, Prepaid Expenses & Other Current Assets, Accounts Payable, \
Accrued Liabilities, Other Current Liabilities, Other Long-Term Liabilities, \
Cash & Equivalents, Non-Operating Assets, Short-Term Debt, Long-Term Debt, \
Share Capital, Retained Earnings, Other Equity (AOCI, Treasury Stock, etc.)

CF: Net Income, D&A Add-back, Amortization of Intangibles Add-back, \
Changes in Working Capital, Operating Cash Flow, Capex, Acquisitions / Disposals, \
Investing Cash Flow, Debt Issuance / Repayment, Dividends Paid, \
Share Issuance / Buyback, Financing Cash Flow, Net Change in Cash

If no safe mapping exists → add to "unmapped_items".

### Numbers
- All values must be floats. Remove currency symbols and thousand separators.
- Negative values: accept "-100" or "(100)", both become -100.0.
- Percentages: convert 15% → 0.15.
- "values" dict MUST be populated for every item — never leave it empty {}.
- If a value is blank/missing for a period, use 0.0.

### Skip
- Skip empty rows, section headers, subtotals that duplicate other rows, \
and any row that is entirely text with no numeric data.
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def document_to_csv(doc: ExtractedDocument, max_rows: int = 500) -> str:
    """Convert extracted document to CSV string, capping total rows to avoid
    context-window overflow on large Excel files."""
    output = io.StringIO()
    writer = csv.writer(output)
    total = 0

    for sheet in doc.sheets:
        writer.writerow([f"--- SHEET: {sheet.name} ---"])
        for row in sheet.rows:
            if total >= max_rows:
                writer.writerow(["... (truncated for length)"])
                break
            writer.writerow([str(x) if x is not None else "" for x in row])
            total += 1
        writer.writerow([])

    return output.getvalue()


def _clean_json(text: str) -> str:
    """Strip markdown fences and leading/trailing whitespace."""
    text = text.strip()
    # Remove ```json ... ``` or ``` ... ```
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Main extraction function
# ---------------------------------------------------------------------------

def run_ai_extraction(
    user_id: str,
    extracted_doc: ExtractedDocument,
    db: Session,
) -> LLMFinancialExtraction:
    """Call the LLM and return a validated LLMFinancialExtraction.

    Uses plain-text JSON prompting (no response_format schema) so it works
    identically with Gemini, Claude, and OpenAI.
    """
    csv_text = document_to_csv(extracted_doc)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "Extract the financial data from the following document and return "
                "the JSON object as instructed. Do not add any other text.\n\n"
                f"=== DOCUMENT START ===\n{csv_text}\n=== DOCUMENT END ==="
            ),
        },
    ]

    # NO response_format — we parse the text ourselves
    res = smart_complete(
        user_id=user_id,
        db=db,
        messages=messages,
        # Generous token budget so Gemini doesn't truncate mid-JSON
        max_tokens=8192,
    )

    content_str = extract_content(res)
    log.info("ai_ingestion_raw_response", chars=len(content_str), preview=content_str[:200])

    cleaned = _clean_json(content_str)

    try:
        data_dict = json.loads(cleaned)
    except json.JSONDecodeError as e:
        # Try to extract the first JSON object from the response in case there's
        # surrounding text the model snuck in despite the instruction
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            try:
                data_dict = json.loads(match.group())
            except json.JSONDecodeError:
                log.error("ai_ingestion_json_parse_failed", error=str(e), content=content_str[:500])
                raise ValueError(f"LLM returned invalid JSON: {e}")
        else:
            log.error("ai_ingestion_no_json_found", content=content_str[:500])
            raise ValueError(f"LLM returned no JSON object. Response: {content_str[:300]}")

    try:
        return LLMFinancialExtraction(**data_dict)
    except Exception as e:
        log.error("ai_ingestion_schema_validation_failed", error=str(e), data=str(data_dict)[:500])
        raise ValueError(f"LLM JSON does not match expected schema: {e}")
