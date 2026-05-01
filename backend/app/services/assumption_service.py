import uuid
from decimal import Decimal
from typing import Dict, List

from sqlalchemy.orm import Session

from app.models.project import AssumptionParam, Entity, HistoricalData, ProjectionAssumption


def seed_default_assumptions(project_id: str, db: Session):
    """Automatically generates default 'flat growth' assumptions based on historical data."""
    
    # 1. Clear existing assumptions to avoid duplicates
    db.query(ProjectionAssumption).filter(ProjectionAssumption.project_id == project_id).delete()
    db.flush()
    
    # 2. Find the primary entity
    entity = db.query(Entity).filter(Entity.project_id == project_id).first()
    if not entity:
        return # Should not happen

    # 3. Fetch latest historical values to use as baseline
    hist_records = db.query(HistoricalData).filter(HistoricalData.project_id == project_id).all()
    if not hist_records:
        return

    latest_vals: Dict[str, Dict[str, Decimal]] = {} # statement_type -> line_item -> last_value
    max_year = max(r.year for r in hist_records)
    
    for r in hist_records:
        if r.year == max_year:
            latest_vals.setdefault(r.statement_type, {})[r.line_item] = Decimal(str(r.value))

    # 4. Default mappings reference (used as documentation; the per-module
    # logic below inlines the values rather than reading from this dict).
    _module_configs = {  # noqa: F841 — kept as in-source documentation
        "revenue": ("PNL", "growth_flat", "growth_rate", 0),
        "cogs": ("PNL", "growth_flat", "growth_rate", 0),
        "opex": ("PNL", "growth_flat", "growth_rate", 0),
        "working_capital": ("BS", "fixed", "value", None), # Use last value
        "capex": ("CF", "fixed", "value", 0),
        "tax": ("PNL", "fixed", "rate", 25),
    }

    # Revenue is special because it can have multiple streams
    rev_items = latest_vals.get("PNL", {})
    for item_name, val in rev_items.items():
        if "revenue" in item_name.lower() or "sales" in item_name.lower() or "income" in item_name.lower():
            _create_assumption(db, project_id, entity.id, "revenue", item_name, "growth_flat", [("growth_rate", 0)])

    # Other PNL items
    for item_name in rev_items:
        if any(kw in item_name.lower() for kw in ["cost of goods", "cogs", "opex", "operating expense", "salaries", "rent"]):
            mod = "cogs" if "cost" in item_name.lower() else "opex"
            _create_assumption(db, project_id, entity.id, mod, item_name, "growth_flat", [("growth_rate", 0)])

    # Balance Sheet (Working Capital)
    bs_items = latest_vals.get("BS", {})
    wc_keys = ["Inventories", "Accounts Receivable", "Accounts Payable", "Accrued Liabilities"]
    for item_name in bs_items:
        if any(k in item_name for k in wc_keys):
            last_val = bs_items[item_name]
            _create_assumption(db, project_id, entity.id, "working_capital", item_name, "fixed", [("value", last_val)])

    db.commit()

def _create_assumption(db: Session, project_id: str, entity_id: str, module: str, line_item: str, method: str, params: List[tuple]):
    a_id = str(uuid.uuid4())
    db.add(ProjectionAssumption(
        id=a_id,
        project_id=project_id,
        entity_id=entity_id,
        module=module,
        line_item=line_item,
        projection_method=method
    ))
    for p_key, p_val in params:
        db.add(AssumptionParam(
            id=str(uuid.uuid4()),
            assumption_id=a_id,
            param_key=p_key,
            value=str(p_val)
        ))
