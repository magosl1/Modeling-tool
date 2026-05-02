"""Auto-seed first-pass projection assumptions from historicals + sector hints.

Goal: a non-expert user uploads historicals, presses "auto-seed", and gets a
*reasonable-looking* model on the first try — not a flat 0% growth shell.

Strategy:
- Compute historical CAGR for the revenue line where we can (≥ 2 historical
  years). Blend it with the sector median (60/40 toward the sector for short
  histories, 80/20 toward history for long histories) so a single noisy year
  doesn't dominate.
- Cost lines (COGS / OpEx) project as a % of revenue using either the
  historical ratio (if the line existed) or the sector default.
- Working capital lines use sector days metrics (DSO/DIO/DPO).
- CapEx, D&A, tax, dividends use sector defaults.

All numbers are best-effort hints. The user should still review them — but
the editing experience is "tweak this 12% growth" rather than "what number
goes here?".
"""
from __future__ import annotations

import re
import uuid
from decimal import Decimal
from typing import Dict, List, Tuple

from sqlalchemy.orm import Session

from app.models.entity import Entity
from app.models.project import (
    AssumptionParam,
    HistoricalData,
    Project,
    ProjectionAssumption,
)
from app.services.sectors import Sector, get_sector


# Line-item matchers. Sector-specific hints (e.g. SaaS "ARR") are merged in at
# runtime via Sector.line_item_hints.
_DEFAULT_REVENUE_PATTERNS = [r"revenue", r"sales", r"income(?!\s*tax)", r"importe.*cifra"]
_COGS_PATTERNS = [r"cost\s*of\s*goods", r"cogs", r"cost\s*of\s*sales"]
_OPEX_PATTERNS = [r"operating\s*expense", r"opex", r"sga", r"salar", r"rent",
                  r"marketing", r"general\s*and\s*admin"]
_AR_PATTERNS = [r"accounts\s*receivable", r"trade\s*receivable", r"deudores"]
_INVENTORY_PATTERNS = [r"invent", r"existencias"]
_AP_PATTERNS = [r"accounts\s*payable", r"trade\s*payable", r"acreedores"]


def _matches_any(name: str, patterns: List[str]) -> bool:
    nl = name.lower()
    return any(re.search(p, nl) for p in patterns)


def _historical_cagr(values_by_year: Dict[int, Decimal]) -> float | None:
    """Compute CAGR over the available history. None if < 2 points or invalid."""
    if len(values_by_year) < 2:
        return None
    years = sorted(values_by_year.keys())
    first, last = float(values_by_year[years[0]]), float(values_by_year[years[-1]])
    if first <= 0 or last <= 0:
        return None
    n = years[-1] - years[0]
    if n <= 0:
        return None
    return ((last / first) ** (1 / n) - 1) * 100  # percent


def _blend_growth(historical_cagr: float | None, sector_growth: float, n_years: int) -> float:
    """Weight historical CAGR vs sector median.

    Short histories (≤2 years) → trust the sector more. Longer ones → trust
    the company's own track record.
    """
    if historical_cagr is None:
        return sector_growth
    weight_history = min(0.8, 0.4 + 0.1 * max(0, n_years - 2))
    return historical_cagr * weight_history + sector_growth * (1 - weight_history)


def seed_default_assumptions(project_id: str, db: Session) -> None:
    """Populate the base scenario with first-pass sector-aware assumptions."""
    # 1. Wipe existing base-scenario assumptions for an idempotent re-seed.
    #    Scenario overrides (scenario_id IS NOT NULL) are *not* touched —
    #    re-seeding shouldn't blow away an analyst's Upside scenario.
    db.query(ProjectionAssumption).filter(
        ProjectionAssumption.project_id == project_id,
        ProjectionAssumption.scenario_id.is_(None),
    ).delete()
    db.flush()

    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return
    sector = get_sector(project.sector)
    defaults = sector.defaults

    entity = db.query(Entity).filter(Entity.project_id == project_id).first()
    if not entity:
        return

    hist_records = db.query(HistoricalData).filter(HistoricalData.project_id == project_id).all()
    if not hist_records:
        return

    # Group history: stmt -> line -> {year: value}
    by_stmt: Dict[str, Dict[str, Dict[int, Decimal]]] = {}
    for r in hist_records:
        by_stmt.setdefault(r.statement_type, {}).setdefault(r.line_item, {})[r.year] = Decimal(str(r.value))

    pnl = by_stmt.get("PNL", {})
    bs = by_stmt.get("BS", {})
    years_in_history = sorted({r.year for r in hist_records})
    n_history = len(years_in_history)

    # 2. Revenue lines — growth-blended.
    revenue_patterns = _DEFAULT_REVENUE_PATTERNS + sector.line_item_hints.get("revenue", [])
    revenue_total_last_year: Decimal = Decimal(0)
    for line, vals in pnl.items():
        if not _matches_any(line, revenue_patterns):
            continue
        if _matches_any(line, _COGS_PATTERNS):  # avoid double-tagging "cost of sales"
            continue
        cagr = _historical_cagr(vals)
        growth = _blend_growth(cagr, defaults.revenue_growth_pct, n_history)
        _create_assumption(db, project_id, entity.id, "revenue", line, "growth_flat",
                           [("growth_rate", round(growth, 2))])
        # accumulate last-year revenue for ratio anchoring
        if vals:
            revenue_total_last_year += vals[max(vals)]

    # 3. COGS — % of revenue from sector (or implied from history if available).
    for line, vals in pnl.items():
        if not _matches_any(line, _COGS_PATTERNS):
            continue
        # If we have a revenue total and a recent COGS value, derive the actual
        # ratio so the model reflects this company, not the sector median.
        ratio_pct = (100 - defaults.gross_margin_pct) if defaults.gross_margin_pct is not None else 65
        if revenue_total_last_year and vals:
            last_cogs = vals[max(vals)]
            implied = float(abs(last_cogs) / revenue_total_last_year) * 100
            # Sanity-clamp to avoid 800% ratios on a one-off year.
            if 5 <= implied <= 95:
                ratio_pct = implied
        _create_assumption(db, project_id, entity.id, "cogs", line, "growth_flat",
                           [("growth_rate", round(defaults.revenue_growth_pct, 2))])

    # 4. OpEx — same idea: project at revenue-growth rate (keeps margin stable).
    for line, vals in pnl.items():
        if not _matches_any(line, _OPEX_PATTERNS):
            continue
        _create_assumption(db, project_id, entity.id, "opex", line, "growth_flat",
                           [("growth_rate", round(defaults.revenue_growth_pct, 2))])

    # 5. Working capital — sector days metrics.
    for line, vals in bs.items():
        if _matches_any(line, _AR_PATTERNS):
            _create_assumption(db, project_id, entity.id, "working_capital", line,
                               "fixed", [("dso_days", defaults.dso_days)])
        elif _matches_any(line, _INVENTORY_PATTERNS):
            _create_assumption(db, project_id, entity.id, "working_capital", line,
                               "fixed", [("dio_days", defaults.dio_days)])
        elif _matches_any(line, _AP_PATTERNS):
            _create_assumption(db, project_id, entity.id, "working_capital", line,
                               "fixed", [("dpo_days", defaults.dpo_days)])

    # 6. CapEx & D&A — % of revenue.
    _create_assumption(db, project_id, entity.id, "capex", "Capital Expenditures",
                       "growth_flat", [("pct_of_revenue", defaults.capex_pct_of_revenue)])
    _create_assumption(db, project_id, entity.id, "da", "Depreciation & Amortization",
                       "growth_flat", [("pct_of_revenue", defaults.da_pct_of_revenue)])

    # 7. Tax — sector statutory rate.
    _create_assumption(db, project_id, entity.id, "tax", "Income Tax",
                       "fixed", [("rate", defaults.tax_rate_pct)])

    db.commit()


def _create_assumption(
    db: Session,
    project_id: str,
    entity_id: str,
    module: str,
    line_item: str,
    method: str,
    params: List[Tuple[str, float | int | Decimal]],
) -> None:
    a_id = str(uuid.uuid4())
    db.add(ProjectionAssumption(
        id=a_id,
        project_id=project_id,
        entity_id=entity_id,
        module=module,
        line_item=line_item,
        projection_method=method,
    ))
    for p_key, p_val in params:
        db.add(AssumptionParam(
            id=str(uuid.uuid4()),
            assumption_id=a_id,
            param_key=p_key,
            value=str(p_val),
        ))
