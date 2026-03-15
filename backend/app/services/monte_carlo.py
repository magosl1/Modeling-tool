"""
Monte Carlo simulation service.

Runs N iterations of the projection engine + DCF engine with user-defined
driver distributions and returns equity value distribution statistics.
"""
import random
import math
from decimal import Decimal
from typing import Dict, List, Optional, Any
from copy import deepcopy

from app.services.projection_engine import ProjectionEngine
from app.services.dcf_engine import DCFEngine

ZERO = Decimal("0")


def _sample(dist: str, params: Dict) -> float:
    """Sample a value from the given distribution."""
    if dist == "normal":
        mean = float(params.get("mean", 0))
        std = float(params.get("std", 1))
        return random.gauss(mean, std)
    elif dist == "triangular":
        low = float(params.get("low", 0))
        mode = float(params.get("mode", 0.5))
        high = float(params.get("high", 1))
        return random.triangular(low, mode, high)
    elif dist == "uniform":
        low = float(params.get("low", 0))
        high = float(params.get("high", 1))
        return random.uniform(low, high)
    else:
        return float(params.get("mean", params.get("value", 0)))


def _apply_driver(assumptions: Dict, driver: str, value: float) -> Dict:
    """Return a modified copy of assumptions with the driver value applied."""
    assumptions = deepcopy(assumptions)
    if driver == "revenue_growth":
        # Apply to all revenue streams as flat growth rate
        streams = assumptions.get("revenue", {}).get("streams", [])
        for s in streams:
            for p in s.get("params", []):
                if p.get("param_key") == "growth_rate":
                    p["value"] = Decimal(str(round(value, 4)))
    elif driver == "gross_margin":
        # Apply as gross_margin_pct for cogs
        cogs = assumptions.setdefault("cogs", {})
        cogs["projection_method"] = "gross_margin_pct"
        cogs["params"] = [{"param_key": "gm_pct", "year": None, "value": Decimal(str(round(value, 4)))}]
    elif driver == "wacc":
        # Store as special key — picked up by DCF layer
        assumptions["_mc_wacc"] = Decimal(str(round(value, 4)))
    elif driver == "terminal_growth":
        assumptions["_mc_terminal_growth"] = Decimal(str(round(value, 4)))
    return assumptions


def run_monte_carlo(
    historical_pnl: Dict,
    historical_bs: Dict,
    historical_cf: Dict,
    historical_years: List[int],
    projection_years: List[int],
    base_assumptions: Dict,
    dcf_inputs: Dict,         # {wacc, terminal_growth_rate, exit_multiple, method, shares_outstanding}
    driver_configs: List[Dict],  # [{driver, distribution, mean, std, ...}]
    n_iterations: int = 1000,
    seed: Optional[int] = None,
) -> Dict:
    """Run Monte Carlo simulation and return distribution statistics."""
    if seed is not None:
        random.seed(seed)

    equity_values: List[float] = []

    for _ in range(n_iterations):
        # Sample all drivers and build perturbed assumptions
        perturbed = deepcopy(base_assumptions)
        perturbed_wacc = float(dcf_inputs.get("wacc", 0.1))
        perturbed_tgr = float(dcf_inputs.get("terminal_growth_rate", 0.02))

        for driver_cfg in driver_configs:
            driver = driver_cfg.get("driver", "")
            dist = driver_cfg.get("distribution", "normal")
            value = _sample(dist, driver_cfg)
            perturbed = _apply_driver(perturbed, driver, value)
            if driver == "wacc":
                perturbed_wacc = value / 100 if value > 1 else value
            elif driver == "terminal_growth":
                perturbed_tgr = value / 100 if value > 1 else value

        try:
            engine = ProjectionEngine(
                historical_pnl=historical_pnl,
                historical_bs=historical_bs,
                historical_cf=historical_cf,
                historical_years=historical_years,
                projection_years=projection_years,
                assumptions=perturbed,
            )
            result = engine.run()
            if result.errors:
                continue

            # Run DCF — use actual DCFEngine signature
            wacc_decimal = Decimal(str(round(perturbed_wacc * 100 if perturbed_wacc < 1 else perturbed_wacc, 4)))
            tgr_decimal = Decimal(str(round(perturbed_tgr * 100 if perturbed_tgr < 1 else perturbed_tgr, 4)))

            dcf = DCFEngine(
                pnl=result.pnl,
                bs=result.bs,
                cf=result.cf,
                projection_years=projection_years,
                wacc=wacc_decimal,
                terminal_growth_rate=tgr_decimal,
                exit_multiple=Decimal(str(dcf_inputs["exit_multiple"])) if dcf_inputs.get("exit_multiple") else None,
                discounting_convention=dcf_inputs.get("discounting_convention", "end_of_year"),
                shares_outstanding=Decimal(str(dcf_inputs["shares_outstanding"])) if dcf_inputs.get("shares_outstanding") else None,
            )
            dcf_result = dcf.run()
            equity_values.append(float(dcf_result.equity_value))
        except Exception:
            continue


    if not equity_values:
        return {"error": "No valid iterations completed", "n_iterations": n_iterations, "n_valid": 0}

    equity_values.sort()
    n = len(equity_values)

    def percentile(data, p):
        idx = (p / 100) * (len(data) - 1)
        lo = int(idx)
        hi = min(lo + 1, len(data) - 1)
        return data[lo] + (idx - lo) * (data[hi] - data[lo])

    mean_val = sum(equity_values) / n
    variance = sum((x - mean_val) ** 2 for x in equity_values) / n
    std_val = math.sqrt(variance)

    # Histogram: 20 bins
    min_v, max_v = equity_values[0], equity_values[-1]
    if max_v == min_v:
        bins = [{"bin_start": min_v, "bin_end": max_v, "count": n}]
    else:
        bin_count = min(20, n)
        bin_size = (max_v - min_v) / bin_count
        bins = []
        for i in range(bin_count):
            lo = min_v + i * bin_size
            hi = lo + bin_size
            count = sum(1 for v in equity_values if lo <= v < hi)
            bins.append({"bin_start": round(lo, 2), "bin_end": round(hi, 2), "count": count})

    return {
        "n_iterations": n_iterations,
        "n_valid": n,
        "p10": round(percentile(equity_values, 10), 2),
        "p25": round(percentile(equity_values, 25), 2),
        "p50": round(percentile(equity_values, 50), 2),
        "p75": round(percentile(equity_values, 75), 2),
        "p90": round(percentile(equity_values, 90), 2),
        "mean": round(mean_val, 2),
        "std": round(std_val, 2),
        "min": round(equity_values[0], 2),
        "max": round(equity_values[-1], 2),
        "histogram": bins,
    }
