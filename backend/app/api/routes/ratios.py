from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.base import get_db
from app.models.user import User
from app.api.deps import get_current_user
from app.api.routes.projections import _get_project, _load_historical
from app.models.project import ProjectedFinancial
from decimal import Decimal

router = APIRouter(prefix="/projects", tags=["ratios"])

@router.get("/{project_id}/ratios")
def get_ratios(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_project(project_id, current_user, db)
    
    pnl_hist, bs_hist, cf_hist, hist_years = _load_historical(project_id, db)
    proj_records = db.query(ProjectedFinancial).filter(ProjectedFinancial.project_id == project_id).all()
    
    # Merge historicals and projections
    merged_data = {"PNL": {}, "BS": {}, "CF": {}}
    
    for stmt_name, stmt_dict in [("PNL", pnl_hist), ("BS", bs_hist), ("CF", cf_hist)]:
        for item, year_vals in stmt_dict.items():
            for yr, val in year_vals.items():
                merged_data[stmt_name].setdefault(item, {})[yr] = Decimal(str(val))
                
    proj_years = set()
    for r in proj_records:
        merged_data[r.statement_type].setdefault(r.line_item, {})[r.year] = Decimal(str(r.value))
        proj_years.add(r.year)
        
    all_years = sorted(list(set(hist_years).union(proj_years)))
    if not all_years:
        return {"ratios": {}, "years": []}
    
    def sdiv(n, d):
        if not d or d == 0: return Decimal(0)
        return n / d
        
    def get_val(stmt, item, year):
        return merged_data[stmt].get(item, {}).get(year, Decimal(0))
        
    ratios = {
        "Margins": {
            "Gross Margin %": {},
            "EBITDA Margin %": {},
            "EBIT Margin %": {},
            "Net Income Margin %": {}
        },
        "Return Ratios": {
            "Return on Assets (ROA) %": {},
            "Return on Equity (ROE) %": {}
        },
        "Liquidity & Leverage": {
            "Current Ratio": {},
            "Debt to Equity": {}
        },
        "Growth Rates": {
            "Revenue Growth %": {},
            "EBIT Growth %": {},
            "Net Income Growth %": {}
        }
    }
    
    for i, yr in enumerate(all_years):
        # PNL
        rev = get_val("PNL", "Revenue", yr)
        gp = get_val("PNL", "Gross Profit", yr)
        ebit = get_val("PNL", "EBIT", yr)
        da = get_val("PNL", "D&A", yr)
        amort = get_val("PNL", "Amortization of Intangibles", yr)
        ebitda = ebit + da + amort
        ni = get_val("PNL", "Net Income", yr)
        
        # Margins
        ratios["Margins"]["Gross Margin %"][yr] = sdiv(gp, rev) * 100
        ratios["Margins"]["EBITDA Margin %"][yr] = sdiv(ebitda, rev) * 100
        ratios["Margins"]["EBIT Margin %"][yr] = sdiv(ebit, rev) * 100
        ratios["Margins"]["Net Income Margin %"][yr] = sdiv(ni, rev) * 100
        
        # BS
        total_assets = get_val("BS", "Net PP&E", yr) + get_val("BS", "Net Intangibles", yr) + \
                       get_val("BS", "Goodwill", yr) + get_val("BS", "Inventories", yr) + \
                       get_val("BS", "Accounts Receivable", yr) + get_val("BS", "Prepaid Expenses & Other Current Assets", yr) + \
                       get_val("BS", "Cash & Equivalents", yr) + get_val("BS", "Non-Operating Assets", yr)
                       
        total_equity = get_val("BS", "Share Capital", yr) + get_val("BS", "Retained Earnings", yr) + get_val("BS", "Other Equity (AOCI, Treasury Stock, etc.)", yr)
        
        current_assets = get_val("BS", "Cash & Equivalents", yr) + get_val("BS", "Accounts Receivable", yr) + \
                         get_val("BS", "Inventories", yr) + get_val("BS", "Prepaid Expenses & Other Current Assets", yr)
                         
        current_liabs = get_val("BS", "Accounts Payable", yr) + get_val("BS", "Accrued Liabilities", yr) + \
                        get_val("BS", "Other Current Liabilities", yr) + get_val("BS", "Short-Term Debt", yr)
                        
        total_debt = get_val("BS", "Short-Term Debt", yr) + get_val("BS", "Long-Term Debt", yr)
        
        # Returns
        ratios["Return Ratios"]["Return on Assets (ROA) %"][yr] = sdiv(ni, total_assets) * 100
        ratios["Return Ratios"]["Return on Equity (ROE) %"][yr] = sdiv(ni, total_equity) * 100
        
        # Liquidity
        ratios["Liquidity & Leverage"]["Current Ratio"][yr] = sdiv(current_assets, current_liabs)
        ratios["Liquidity & Leverage"]["Debt to Equity"][yr] = sdiv(total_debt, total_equity)
        
        # Growth
        if i > 0:
            prev_yr = all_years[i-1]
            prev_rev = get_val("PNL", "Revenue", prev_yr)
            prev_ebit = get_val("PNL", "EBIT", prev_yr)
            prev_ni = get_val("PNL", "Net Income", prev_yr)
            
            ratios["Growth Rates"]["Revenue Growth %"][yr] = (sdiv(rev, prev_rev) - 1) * 100 if prev_rev else Decimal(0)
            ratios["Growth Rates"]["EBIT Growth %"][yr] = (sdiv(ebit, prev_ebit) - 1) * 100 if prev_ebit else Decimal(0)
            ratios["Growth Rates"]["Net Income Growth %"][yr] = (sdiv(ni, prev_ni) - 1) * 100 if prev_ni else Decimal(0)
        else:
            ratios["Growth Rates"]["Revenue Growth %"][yr] = Decimal(0)
            ratios["Growth Rates"]["EBIT Growth %"][yr] = Decimal(0)
            ratios["Growth Rates"]["Net Income Growth %"][yr] = Decimal(0)
            
    res = {}
    for cat, metrics in ratios.items():
        res[cat] = {}
        for m, year_vals in metrics.items():
            res[cat][m] = {y: str(round(val, 2)) for y, val in year_vals.items()}
            
    return {"ratios": res, "years": all_years}
