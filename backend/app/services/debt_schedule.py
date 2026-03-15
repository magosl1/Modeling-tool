"""
Debt Schedule Service — Revolver + Term Loan Cash Sweep.

Builds a year-by-year debt schedule with:
- Revolving credit facility: auto-draws when cash < min_cash, repays when excess cash
- Fixed-tranche term loans: bullet or straight-line amortization
- Iterative convergence (max 10 iterations) for interest ↔ cash circularity
"""
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional, Any

ZERO = Decimal("0")
TWO = Decimal("2")
CONVERGENCE_DELTA = Decimal("0.01")
MAX_ITER = 10


def d(val) -> Decimal:
    if val is None:
        return ZERO
    return Decimal(str(val))


def build_debt_schedule(
    proj_years: List[int],
    revolver_config: Optional[Dict],        # {limit, rate, min_cash}
    tranches: List[Dict],                   # [{name, principal, rate, maturity_year, method}]
    pre_interest_ebit: Dict[int, Decimal],  # EBIT before interest (from engine step 6)
    wc_change: Dict[int, Decimal],          # Δworking capital per year (from engine step 17)
    capex: Dict[int, Decimal],              # capex per year
    tax_rate: Decimal,                      # simplified flat rate for convergence
    dividends: Dict[int, Decimal],          # dividends per year
    opening_cash: Decimal,                   # cash at start of first projection year
) -> Dict[int, Dict]:
    """
    Returns per year:
    {
      year: {
        revolver_draw: Decimal,
        revolver_repay: Decimal,
        revolver_balance: Decimal,
        term_loan_amortization: Decimal,
        interest_expense: Decimal,   (total, negative)
        cash_end: Decimal,
      }
    }
    """
    if not revolver_config and not tranches:
        return {}

    rev_limit = d(revolver_config.get("limit", 0)) if revolver_config else ZERO
    rev_rate = d(revolver_config.get("rate", 0)) if revolver_config else ZERO
    min_cash = d(revolver_config.get("min_cash", 0)) if revolver_config else ZERO

    # Build tranche schedules
    tranche_balances: Dict[str, Decimal] = {}
    for t in tranches:
        tranche_balances[t["id"]] = d(t["principal"])

    result: Dict[int, Dict] = {}
    cash = opening_cash
    revolver_bal = ZERO

    for year in proj_years:
        ebit = pre_interest_ebit.get(year, ZERO)
        delta_wc = wc_change.get(year, ZERO)
        cap = capex.get(year, ZERO)
        div = dividends.get(year, ZERO)

        # Iterative convergence
        interest_guess = ZERO
        for _iter in range(MAX_ITER):
            # Approximate tax on EBT
            ebt = ebit + interest_guess  # interest_guess is negative
            tax = max(ZERO, ebt * tax_rate / 100) if ebt > ZERO else ZERO

            # Approximate net income
            ni = ebt - tax

            # Approximate operating cash flow
            ocf = ni + delta_wc   # simplified: ignores D&A add-back for convergence

            # Investing
            icf = -cap

            # Term loan amortization this year
            tl_amort = ZERO
            for t in tranches:
                t_bal = tranche_balances[t["id"]]
                if t_bal <= ZERO:
                    continue
                mat = t.get("maturity_year", year)
                method = t.get("amortization_method", "bullet")
                if method == "bullet":
                    if year == mat:
                        tl_amort += t_bal
                elif method == "straight_line":
                    start_yr = proj_years[0]
                    remaining = mat - start_yr + 1
                    if remaining > 0:
                        tl_amort += d(t["principal"]) / remaining

            # Financing (without revolver yet)
            fin_base = -tl_amort - div

            # Pre-revolver cash
            pre_rev_cash = cash + ocf + icf + fin_base

            # Revolver logic
            if pre_rev_cash < min_cash:
                needed = min_cash - pre_rev_cash
                draw = min(needed, rev_limit - revolver_bal)
                repay = ZERO
            else:
                draw = ZERO
                # Repay excess
                excess = pre_rev_cash - min_cash
                repay = min(excess, revolver_bal)

            # Interest: term loans + revolver
            tl_interest = ZERO
            for t in tranches:
                bal = tranche_balances[t["id"]]
                if bal > ZERO:
                    tl_interest -= bal * d(t["rate"]) / 100
            rev_interest = -(revolver_bal + draw - repay) * rev_rate / 100

            new_interest = tl_interest + rev_interest

            if abs(new_interest - interest_guess) < CONVERGENCE_DELTA:
                interest_guess = new_interest
                break
            interest_guess = new_interest

        # Finalize year
        ebt_final = ebit + interest_guess
        tax_final = max(ZERO, ebt_final * tax_rate / 100) if ebt_final > ZERO else ZERO
        ni_final = ebt_final - tax_final
        ocf_final = ni_final + delta_wc

        # Apply tranche amortization
        tl_amort_final = ZERO
        for t in tranches:
            t_id = t["id"]
            t_bal = tranche_balances[t_id]
            if t_bal <= ZERO:
                continue
            mat = t.get("maturity_year", year)
            method = t.get("amortization_method", "bullet")
            if method == "bullet":
                if year == mat:
                    amt = t_bal
                    tl_amort_final += amt
                    tranche_balances[t_id] = ZERO
            elif method == "straight_line":
                start_yr = proj_years[0]
                remaining = mat - start_yr + 1
                if remaining > 0:
                    amt = min(d(t["principal"]) / remaining, t_bal)
                    tl_amort_final += amt
                    tranche_balances[t_id] = max(ZERO, t_bal - amt)

        # Revolver
        if (cash + ocf_final - cap - tl_amort_final - div) < min_cash:
            draw_final = min(min_cash - (cash + ocf_final - cap - tl_amort_final - div), rev_limit - revolver_bal)
            repay_final = ZERO
        else:
            draw_final = ZERO
            repay_final = min((cash + ocf_final - cap - tl_amort_final - div) - min_cash, revolver_bal)

        revolver_bal = max(ZERO, revolver_bal + draw_final - repay_final)
        cash_end = cash + ocf_final - cap - tl_amort_final - div + draw_final - repay_final

        result[year] = {
            "revolver_draw": draw_final,
            "revolver_repay": repay_final,
            "revolver_balance": revolver_bal,
            "term_loan_amortization": tl_amort_final,
            "interest_expense": interest_guess,  # already negative
            "cash_end": cash_end,
        }
        cash = cash_end

    return result
