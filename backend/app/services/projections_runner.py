from decimal import Decimal
from typing import Dict

from sqlalchemy.orm import Session, joinedload

from app.models.project import HistoricalData, ProjectionAssumption, Project
from app.services.projection_engine import ProjectionEngine

_PNL_EXPENSE_ITEMS = [
    "Cost of Goods Sold", "SG&A", "R&D", "D&A", 
    "Amortization of Intangibles", "Other OpEx", 
    "Interest Expense", "Tax"
]

def load_historical(project_id: str, db: Session) -> tuple:
    records = db.query(HistoricalData).filter(HistoricalData.project_id == project_id).all()
    pnl, bs, cf = {}, {}, {}
    years = set()
    for r in records:
        val = Decimal(str(r.value))
        if r.statement_type in ("BS", "CF") or r.line_item in _PNL_EXPENSE_ITEMS:
            val = abs(val)

        year = r.year
        years.add(year)
        if r.statement_type == "PNL":
            pnl.setdefault(r.line_item, {})[year] = val
        elif r.statement_type == "BS":
            bs.setdefault(r.line_item, {})[year] = val
        elif r.statement_type == "CF":
            cf.setdefault(r.line_item, {})[year] = val
    return pnl, bs, cf, sorted(years)

def transform_assumptions(raw: Dict[str, list]) -> Dict:
    result: Dict = {}
    if "revenue" in raw:
        streams = []
        for item in raw["revenue"]:
            streams.append({
                "stream_name": item["line_item"],
                "projection_method": item["projection_method"],
                "params": item["params"],
            })
        result["revenue"] = {"streams": streams}

    if "cogs" in raw and raw["cogs"]:
        item = raw["cogs"][0]
        result["cogs"] = {
            "projection_method": item["projection_method"],
            "params": item["params"],
        }

    if "opex" in raw:
        result["opex"] = {"items": raw["opex"]}

    if "da" in raw:
        da_result: Dict = {}
        for item in raw["da"]:
            li = item["line_item"]
            if "depreciation" in li.lower() or li == "D&A":
                da_result["depreciation"] = {
                    "method": item["projection_method"],
                    "params": item["params"],
                }
            if "amortization" in li.lower():
                da_result["amortization"] = {
                    "method": item["projection_method"],
                    "params": item["params"],
                }
        result["da"] = da_result

    if "working_capital" in raw:
        WC_KEY_MAP = {
            "Inventories": "inventories",
            "Accounts Receivable": "accounts_receivable",
            "Prepaid Expenses & Other Current Assets": "prepaid",
            "Accounts Payable": "accounts_payable",
            "Accrued Liabilities": "accrued_liabilities",
            "Other Current Liabilities": "other_current_liabilities",
        }
        wc_result: Dict = {}
        for item in raw["working_capital"]:
            key = WC_KEY_MAP.get(item["line_item"])
            if key:
                wc_result[key] = {
                    "method": item["projection_method"],
                    "params": item["params"],
                }
        result["working_capital"] = wc_result

    if "capex" in raw and raw["capex"]:
        item = raw["capex"][0]
        result["capex"] = {
            "projection_method": item["projection_method"],
            "params": item["params"],
        }

    if "debt" in raw and raw["debt"]:
        item = raw["debt"][0]
        method = item["projection_method"]
        debt_result: Dict = {
            "projection_method": method,
            "params": item["params"],
            "interest_rate": {"method": "fixed", "params": []},
        }
        for p in item["params"]:
            if p["param_key"] == "interest_rate":
                debt_result["interest_rate"] = {
                    "method": "fixed",
                    "params": [{"param_key": "rate", "year": p["year"], "value": p["value"]}],
                }
        result["debt"] = debt_result

    if "tax" in raw and raw["tax"]:
        item = raw["tax"][0]
        result["tax"] = {
            "projection_method": item["projection_method"],
            "params": item["params"],
        }

    if "dividends" in raw and raw["dividends"]:
        item = raw["dividends"][0]
        result["dividends"] = {
            "projection_method": item["projection_method"],
            "params": item["params"],
        }

    if "interest_income" in raw and raw["interest_income"]:
        item = raw["interest_income"][0]
        result["interest_income"] = {
            "projection_method": item["projection_method"],
            "params": item["params"],
        }

    if "non_operating" in raw:
        nonop_result: Dict = {}
        for item in raw["non_operating"]:
            li = item["line_item"]
            if "non-operating assets" in li.lower() or "non_operating_assets" in li.lower():
                nonop_result["non_operating_assets"] = {
                    "method": item["projection_method"],
                    "params": item["params"],
                }
            elif "goodwill" in li.lower():
                nonop_result["goodwill"] = {
                    "method": item["projection_method"],
                    "params": item["params"],
                }
            elif "other non-operating" in li.lower() or "non-operating income" in li.lower():
                nonop_result["other_nonop_pl"] = {
                    "method": item["projection_method"],
                    "params": item["params"],
                }
            elif "equity" in li.lower():
                nonop_result["equity"] = {
                    "method": item["projection_method"],
                    "params": item["params"],
                }
        result["non_operating"] = nonop_result

    return result

def load_assumptions(project_id: str, db: Session) -> Dict:
    assumptions_db = (
        db.query(ProjectionAssumption)
        .options(joinedload(ProjectionAssumption.params))
        .filter(ProjectionAssumption.project_id == project_id)
        .all()
    )

    raw: Dict[str, list] = {}
    for a in assumptions_db:
        params = [{"param_key": p.param_key, "year": p.year, "value": Decimal(str(p.value))} for p in a.params]
        raw.setdefault(a.module, []).append({
            "line_item": a.line_item,
            "projection_method": a.projection_method,
            "params": params,
        })

    return transform_assumptions(raw)

def run_projection_engine(project: Project, pnl: dict, bs: dict, cf: dict,
                            hist_years: list, assumptions: dict):
    last_hist_year = hist_years[-1] if hist_years else 2023
    proj_years = list(range(last_hist_year + 1, last_hist_year + 1 + project.projection_years))

    engine = ProjectionEngine(
        historical_pnl=pnl,
        historical_bs=bs,
        historical_cf=cf,
        historical_years=hist_years,
        projection_years=proj_years,
        assumptions=assumptions,
    )
    return engine.run(), proj_years
