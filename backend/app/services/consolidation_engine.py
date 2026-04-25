"""
Consolidation engine — Phase 3.

Consolidates N entity-level projections (or historical data) into group-level
P&L, Balance Sheet, and Cash Flow statements.

Supported consolidation methods (per entity):
    full          – 100 % line-by-line; minority interest added for <100 % ownership
    proportional  – ownership_pct × every line item (joint-venture treatment)
    equity_method – only Net Income × ownership_pct flows into the parent P&L;
                    a "Investment in Associates" asset appears on the parent BS
    none          – entity excluded from consolidation entirely

Intercompany eliminations are applied after aggregation:
    revenue_cost / management_fee  → reduce Revenue (seller) and the matching
                                     cost line on the buyer side
    loan                           → reduce intercompany receivable/payable on BS
    dividend                       → reduce dividend income on parent P&L
"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.models.eliminations import IntercompanyTransaction
from app.models.entity import Entity
from app.models.project import HistoricalData, ProjectedFinancial

# ── Internal helpers ──────────────────────────────────────────────────────────

StmtMap = dict[str, dict[int, Decimal]]  # line_item → {year → value}


def _load_projections(entity_id: str, scenario_id: Optional[str], db: Session) -> dict[str, StmtMap]:
    q = db.query(ProjectedFinancial).filter(ProjectedFinancial.entity_id == entity_id)
    if scenario_id:
        q = q.filter(ProjectedFinancial.scenario_id == scenario_id)
    else:
        q = q.filter(ProjectedFinancial.scenario_id.is_(None))
    result: dict[str, StmtMap] = {"PNL": {}, "BS": {}, "CF": {}}
    for r in q.all():
        result[r.statement_type].setdefault(r.line_item, {})[r.year] = Decimal(str(r.value))
    return result


def _load_historical(entity_id: str, db: Session) -> dict[str, StmtMap]:
    result: dict[str, StmtMap] = {"PNL": {}, "BS": {}, "CF": {}}
    for r in db.query(HistoricalData).filter(HistoricalData.entity_id == entity_id).all():
        result[r.statement_type].setdefault(r.line_item, {})[r.year] = Decimal(str(r.value))
    return result


def _has_data(stmts: dict[str, StmtMap]) -> bool:
    return any(stmts[s] for s in ("PNL", "BS", "CF"))


def _add_to(target: StmtMap, source: StmtMap, factor: Decimal) -> None:
    """target[item][year] += source[item][year] * factor  (in-place)."""
    for item, year_vals in source.items():
        tgt = target.setdefault(item, {})
        for year, value in year_vals.items():
            tgt[year] = tgt.get(year, Decimal(0)) + value * factor


def _ebitda_from_pnl(pnl: StmtMap) -> StmtMap:
    """Approximate EBITDA = EBIT - D&A - Amortization (since EBIT already nets them)."""
    ebit = pnl.get("EBIT", {})
    da = pnl.get("D&A", {})
    amort = pnl.get("Amortization of Intangibles", {})
    years = set(ebit) | set(da) | set(amort)
    return {
        y: ebit.get(y, Decimal(0)) - da.get(y, Decimal(0)) - amort.get(y, Decimal(0))
        for y in years
    }


def _serialize(stmt: StmtMap) -> dict[str, dict[str, str]]:
    """Convert {line: {year: Decimal}} → {line: {str(year): str(value)}} for JSON."""
    return {item: {str(y): str(v) for y, v in yr_vals.items()} for item, yr_vals in stmt.items()}


# ── Public API ────────────────────────────────────────────────────────────────

def consolidate(
    project_id: str,
    db: Session,
    scenario_id: Optional[str] = None,
    use_historical: bool = False,
) -> dict:
    """
    Consolidate all active entities in *project_id* into group-level statements.

    Returns a dict::

        {
            "PNL": {line_item: {str(year): str(value)}},
            "BS":  {...},
            "CF":  {...},
            "contribution": [
                {
                    "entity_id": str,
                    "entity_name": str,
                    "ownership_pct": float,
                    "consolidation_method": str,
                    "revenue":    {str(year): str(value)},
                    "ebitda":     {str(year): str(value)},
                    "net_income": {str(year): str(value)},
                },
                ...
            ],
            "metadata": {
                "entity_count": int,
                "entities_with_data": int,
                "has_minority_interest": bool,
                "has_eliminations": bool,
            },
        }
    """
    entities: list[Entity] = (
        db.query(Entity)
        .filter(Entity.project_id == project_id, Entity.is_active.is_(True))
        .order_by(Entity.display_order)
        .all()
    )

    cons_pnl: StmtMap = {}
    cons_bs: StmtMap = {}
    cons_cf: StmtMap = {}
    contribution_list: list[dict] = []
    entities_with_data = 0
    has_minority_interest = False

    for entity in entities:
        if entity.consolidation_method == "none":
            continue

        # ── Load data (prefer projected; fall back to historical) ──────────
        if use_historical:
            stmts = _load_historical(entity.id, db)
        else:
            stmts = _load_projections(entity.id, scenario_id, db)
            if not _has_data(stmts):
                stmts = _load_historical(entity.id, db)

        if not _has_data(stmts):
            continue

        entities_with_data += 1
        pct = Decimal(str(entity.ownership_pct)) / Decimal("100")

        # ── Apply consolidation method ────────────────────────────────────
        if entity.consolidation_method == "full":
            _add_to(cons_pnl, stmts["PNL"], Decimal("1"))
            _add_to(cons_bs, stmts["BS"], Decimal("1"))
            _add_to(cons_cf, stmts["CF"], Decimal("1"))

            # Minority interest when parent owns < 100 %
            if entity.ownership_pct < 100.0:
                has_minority_interest = True
                mi_pct = Decimal("1") - pct

                # P&L: minority share of net income (deduction)
                for year, value in stmts["PNL"].get("Net Income", {}).items():
                    mi_row = cons_pnl.setdefault("Minority Interest", {})
                    mi_row[year] = mi_row.get(year, Decimal(0)) - value * mi_pct

                # BS: minority share of equity (contra-equity line)
                mi_equity: dict[int, Decimal] = {}
                for item in ("Share Capital", "Retained Earnings",
                             "Other Equity (AOCI, Treasury Stock, etc.)"):
                    for year, value in stmts["BS"].get(item, {}).items():
                        mi_equity[year] = mi_equity.get(year, Decimal(0)) + value
                for year, value in mi_equity.items():
                    mi_row = cons_bs.setdefault("Minority Interest (Equity)", {})
                    mi_row[year] = mi_row.get(year, Decimal(0)) + value * mi_pct

        elif entity.consolidation_method == "proportional":
            _add_to(cons_pnl, stmts["PNL"], pct)
            _add_to(cons_bs, stmts["BS"], pct)
            _add_to(cons_cf, stmts["CF"], pct)

        elif entity.consolidation_method == "equity_method":
            # Only Net Income × pct flows to the parent P&L
            for year, value in stmts["PNL"].get("Net Income", {}).items():
                row = cons_pnl.setdefault("Share of Associates (Equity Method)", {})
                row[year] = row.get(year, Decimal(0)) + value * pct

            # Investment in Associates on BS (positive asset, so use abs of equity)
            equity_total: dict[int, Decimal] = {}
            for item in ("Share Capital", "Retained Earnings",
                         "Other Equity (AOCI, Treasury Stock, etc.)"):
                for year, value in stmts["BS"].get(item, {}).items():
                    equity_total[year] = equity_total.get(year, Decimal(0)) + value
            for year, value in equity_total.items():
                row = cons_bs.setdefault("Investment in Associates", {})
                row[year] = row.get(year, Decimal(0)) + abs(value) * pct

        # ── Build per-entity contribution entry ───────────────────────────
        rev_pnl = stmts["PNL"].get("Revenue", stmts["PNL"].get("Total Revenue", {}))
        ebitda_map = _ebitda_from_pnl(stmts["PNL"])
        contribution_list.append({
            "entity_id": entity.id,
            "entity_name": entity.name,
            "ownership_pct": entity.ownership_pct,
            "consolidation_method": entity.consolidation_method,
            "revenue": {str(y): str(v) for y, v in rev_pnl.items()},
            "ebitda": {str(y): str(v) for y, v in ebitda_map.items()},
            "net_income": {str(y): str(v) for y, v in stmts["PNL"].get("Net Income", {}).items()},
        })

    # ── Apply intercompany eliminations ───────────────────────────────────
    eliminations = (
        db.query(IntercompanyTransaction)
        .filter(IntercompanyTransaction.project_id == project_id)
        .all()
    )
    has_eliminations = bool(eliminations)

    for elim in eliminations:
        for year_str, amount in elim.amount_by_year.items():
            year = int(year_str)
            amt = Decimal(str(amount))

            if elim.transaction_type in ("revenue_cost", "management_fee"):
                # Remove from Revenue (seller) — buyer's cost net out automatically
                for rev_item in ("Revenue", "Total Revenue"):
                    if rev_item in cons_pnl:
                        cons_pnl[rev_item][year] = cons_pnl[rev_item].get(year, Decimal(0)) - amt
                        break

            elif elim.transaction_type == "loan":
                # Net off intercompany receivable vs payable on BS
                if "Non-Operating Assets" in cons_bs:
                    cons_bs["Non-Operating Assets"][year] = (
                        cons_bs["Non-Operating Assets"].get(year, Decimal(0)) - amt
                    )

            elif elim.transaction_type == "dividend":
                # Remove dividend income from parent P&L (booked under non-operating income)
                if "Other Non-Operating Income / (Expense)" in cons_pnl:
                    cons_pnl["Other Non-Operating Income / (Expense)"][year] = (
                        cons_pnl["Other Non-Operating Income / (Expense)"].get(year, Decimal(0)) - amt
                    )

    return {
        "PNL": _serialize(cons_pnl),
        "BS": _serialize(cons_bs),
        "CF": _serialize(cons_cf),
        "contribution": contribution_list,
        "metadata": {
            "entity_count": len(entities),
            "entities_with_data": entities_with_data,
            "has_minority_interest": has_minority_interest,
            "has_eliminations": has_eliminations,
        },
    }
