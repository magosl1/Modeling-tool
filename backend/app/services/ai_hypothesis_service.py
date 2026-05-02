"""AI Hypothesis Engine — first-pass projection model from historicals + sector.

The non-AI auto-seed (assumption_service.seed_default_assumptions) gives every
new project a reasonable shell. This service goes one step further: it asks an
LLM to *reason* about the historicals and the sector's economic logic, then
emits a tailored set of assumptions with a one-line rationale per item.

Design decisions:
- The LLM never sees raw monetary amounts. We send only:
    * the sector card (label + median ratios),
    * line-item names (P&L / BS / CF row labels), and
    * normalised ratios derived from history (CAGR, gross margin %, opex %,
      capex %, days WC, etc.)
  Sending normalised ratios — not amounts — keeps prompts short, keeps
  proprietary numbers out of the upstream provider, and lets cheap models
  reason effectively.
- The LLM returns structured JSON conforming to a Pydantic schema. We never
  trust freeform text.
- Output is persisted into the **base scenario only**. Override scenarios are
  preserved.
"""
from __future__ import annotations

import re
import statistics
import uuid
from decimal import Decimal
from typing import Dict, List, Optional

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.entity import Entity
from app.models.project import (
    AssumptionParam,
    HistoricalData,
    Project,
    ProjectionAssumption,
)
from app.services.llm_client import smart_complete
from app.services.sectors import Sector, get_sector

log = get_logger("app.ai_hypothesis")


# ---------------------------------------------------------------------------
# Pydantic schemas — strict shape the LLM must return
# ---------------------------------------------------------------------------

class _HypothesisParam(BaseModel):
    param_key: str = Field(description="One of: growth_rate, pct_of_revenue, dso_days, dio_days, dpo_days, rate, value")
    value: float = Field(description="Numeric value matching the param_key (e.g. 8.5 for 8.5%, 45 for 45 days)")


class _HypothesisItem(BaseModel):
    module: str = Field(description="One of: revenue, cogs, opex, da, working_capital, capex, debt, tax, dividends")
    line_item: str = Field(description="Exact line item name from the supplied list")
    projection_method: str = Field(description="One of: growth_flat, fixed")
    params: List[_HypothesisParam]
    rationale: str = Field(max_length=400, description="Short justification (≤2 sentences) tying the value to history and/or sector context")


class HypothesisResponse(BaseModel):
    items: List[_HypothesisItem]


# ---------------------------------------------------------------------------
# History → ratio summary
# ---------------------------------------------------------------------------

_REVENUE_RX = re.compile(r"revenue|sales|importe.*cifra|^arr$|^mrr$", re.I)
_COGS_RX = re.compile(r"cost\s*of\s*(goods|sales|revenue)|cogs", re.I)
_OPEX_RX = re.compile(r"operating\s*expense|opex|sga|salar|rent|marketing|general\s*and\s*admin", re.I)
_AR_RX = re.compile(r"accounts\s*receivable|trade\s*receivable|deudores", re.I)
_INV_RX = re.compile(r"invent|existencias", re.I)
_AP_RX = re.compile(r"accounts\s*payable|trade\s*payable|acreedores", re.I)
_CAPEX_RX = re.compile(r"capital\s*expenditure|capex|purchase.*property", re.I)


def _summarise_history(records: List[HistoricalData]) -> Dict:
    """Build a compact ratio summary the LLM can reason on without seeing $."""
    by_stmt: Dict[str, Dict[str, Dict[int, Decimal]]] = {}
    for r in records:
        by_stmt.setdefault(r.statement_type, {}).setdefault(r.line_item, {})[r.year] = Decimal(str(r.value))

    pnl, bs, cf = by_stmt.get("PNL", {}), by_stmt.get("BS", {}), by_stmt.get("CF", {})
    years = sorted({r.year for r in records})

    def cagr(vals: Dict[int, Decimal]) -> Optional[float]:
        if len(vals) < 2:
            return None
        ks = sorted(vals.keys())
        first, last = float(vals[ks[0]]), float(vals[ks[-1]])
        if first <= 0 or last <= 0:
            return None
        return round(((last / first) ** (1 / (ks[-1] - ks[0])) - 1) * 100, 2)

    # Total revenue per year (sum of any line that matches the revenue regex).
    rev_by_year: Dict[int, float] = {}
    for line, vals in pnl.items():
        if _REVENUE_RX.search(line) and not _COGS_RX.search(line):
            for y, v in vals.items():
                rev_by_year[y] = rev_by_year.get(y, 0) + float(v)

    revenue_cagr = cagr({y: Decimal(str(v)) for y, v in rev_by_year.items()}) if rev_by_year else None

    def avg_ratio(matcher: re.Pattern, source: Dict) -> Optional[float]:
        ratios: List[float] = []
        for line, vals in source.items():
            if not matcher.search(line):
                continue
            for y, v in vals.items():
                if rev_by_year.get(y):
                    ratios.append(abs(float(v)) / rev_by_year[y] * 100)
        return round(statistics.mean(ratios), 2) if ratios else None

    return {
        "history_years": years,
        "revenue_lines": [l for l in pnl if _REVENUE_RX.search(l) and not _COGS_RX.search(l)],
        "cogs_lines": [l for l in pnl if _COGS_RX.search(l)],
        "opex_lines": [l for l in pnl if _OPEX_RX.search(l)],
        "ar_lines": [l for l in bs if _AR_RX.search(l)],
        "inventory_lines": [l for l in bs if _INV_RX.search(l)],
        "ap_lines": [l for l in bs if _AP_RX.search(l)],
        "capex_lines": [l for l in cf if _CAPEX_RX.search(l)],
        "metrics": {
            "revenue_cagr_pct": revenue_cagr,
            "avg_cogs_pct_of_revenue": avg_ratio(_COGS_RX, pnl),
            "avg_opex_pct_of_revenue": avg_ratio(_OPEX_RX, pnl),
            "avg_capex_pct_of_revenue": avg_ratio(_CAPEX_RX, cf),
        },
    }


def _build_prompt(sector: Sector, history_summary: Dict, projection_years: int) -> List[Dict]:
    """Compose the chat messages for the LLM call."""
    d = sector.defaults
    sector_card = (
        f"Sector: {sector.label} ({sector.id})\n"
        f"Description: {sector.description}\n"
        f"Sector medians: revenue growth {d.revenue_growth_pct}%, "
        f"gross margin {d.gross_margin_pct}%, opex {d.opex_pct_of_revenue}% of revenue, "
        f"capex {d.capex_pct_of_revenue}% of revenue, D&A {d.da_pct_of_revenue}% of revenue, "
        f"DSO {d.dso_days}d, DIO {d.dio_days}d, DPO {d.dpo_days}d, "
        f"tax {d.tax_rate_pct}%."
    )
    sys = (
        "You are a financial-analysis assistant generating a first-pass projection "
        "model. Return ONLY a JSON object matching the schema. Each assumption "
        "must include a short rationale referencing either the company's history "
        "or the sector context. Be conservative when historical signal is weak."
    )
    user = (
        f"{sector_card}\n\n"
        f"Company history summary (NO raw amounts shared):\n"
        f"  Years: {history_summary['history_years']}\n"
        f"  Revenue lines: {history_summary['revenue_lines']}\n"
        f"  COGS lines: {history_summary['cogs_lines']}\n"
        f"  OpEx lines: {history_summary['opex_lines']}\n"
        f"  Working-capital lines: AR={history_summary['ar_lines']} "
        f"INV={history_summary['inventory_lines']} AP={history_summary['ap_lines']}\n"
        f"  CapEx lines: {history_summary['capex_lines']}\n"
        f"  Implied historical ratios: {history_summary['metrics']}\n\n"
        f"Generate assumptions for a {projection_years}-year projection. "
        "For revenue lines blend historical CAGR with the sector median (lean on "
        "history if it looks stable, on the sector if data is thin). For COGS/OpEx "
        "use growth_flat at a rate that holds margins. For working capital use "
        "fixed days metrics from the sector. For capex/D&A use pct_of_revenue."
    )
    return [
        {"role": "system", "content": sys},
        {"role": "user", "content": user},
    ]


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate_hypothesis(project_id: str, user_id: str, db: Session) -> Dict:
    """Run the AI hypothesis engine and persist results to the base scenario.

    Returns a summary suitable for the UI: counts, a short narrative, and the
    list of items with rationales (also persisted on each ProjectionAssumption).
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise ValueError("Project not found")

    sector = get_sector(project.sector)
    records = db.query(HistoricalData).filter(HistoricalData.project_id == project_id).all()
    if not records:
        raise ValueError("No historical data uploaded — cannot generate hypothesis")

    summary = _summarise_history(records)
    messages = _build_prompt(sector, summary, project.projection_years)

    log.info("ai_hypothesis_call", project_id=project_id, sector=sector.id, history_years=len(summary["history_years"]))
    response = smart_complete(user_id, db, messages, response_format=HypothesisResponse, max_tokens=4096)

    # Parse: smart_complete returns the raw provider response. We expect the
    # content to be a JSON string matching HypothesisResponse.
    import json
    raw = response["choices"][0]["message"]["content"]
    if isinstance(raw, str):
        raw = json.loads(raw)
    parsed = HypothesisResponse.model_validate(raw)

    # Persist into the base scenario, replacing existing base assumptions.
    # Override scenarios (scenario_id IS NOT NULL) are left untouched so the
    # analyst's experiments survive a re-run.
    entity = db.query(Entity).filter(Entity.project_id == project_id).first()
    if not entity:
        raise ValueError("Project has no entity")

    db.query(ProjectionAssumption).filter(
        ProjectionAssumption.project_id == project_id,
        ProjectionAssumption.scenario_id.is_(None),
    ).delete()
    db.flush()

    persisted = 0
    for item in parsed.items:
        a_id = str(uuid.uuid4())
        db.add(ProjectionAssumption(
            id=a_id,
            project_id=project_id,
            entity_id=entity.id,
            scenario_id=None,
            module=item.module,
            line_item=item.line_item,
            projection_method=item.projection_method,
            rationale=item.rationale,
        ))
        for p in item.params:
            db.add(AssumptionParam(
                id=str(uuid.uuid4()),
                assumption_id=a_id,
                param_key=p.param_key,
                value=str(p.value),
            ))
        persisted += 1

    db.commit()
    log.info("ai_hypothesis_persisted", project_id=project_id, items=persisted)

    return {
        "sector": sector.label,
        "items_persisted": persisted,
        "history_summary": summary,
        "items": [item.model_dump() for item in parsed.items],
    }
