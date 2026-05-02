"""Sector catalog and per-sector default assumptions.

The catalog drives two product surfaces:

1. The sector picker on project creation (UI lists `SECTORS`).
2. The auto-seed routine that produces a first-pass projection model when the
   user uploads historicals. The numbers here are deliberately middle-of-the-
   road industry medians — good enough to give a non-expert analyst a model
   that *looks reasonable* on day one, with the expectation they will tweak
   from there. They are not meant to be authoritative benchmarks.

When in doubt, prefer assumptions that are conservative (slightly lower
growth, slightly higher cost ratios) so the headline valuation isn't
artificially flattering.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class SectorDefaults:
    """Per-sector hint values used by the auto-seed engine.

    All percentages are expressed as *percent* (e.g. 8 = 8%) to match the
    convention the assumption UI uses on input. Days metrics (DSO/DIO/DPO)
    are in days. WACC/terminal growth are also percent.
    """
    revenue_growth_pct: float
    gross_margin_pct: Optional[float] = None      # if None, opex_pct_of_revenue is used instead
    opex_pct_of_revenue: float = 25.0
    da_pct_of_revenue: float = 4.0
    capex_pct_of_revenue: float = 5.0
    dso_days: int = 45                            # days sales outstanding
    dio_days: int = 30                            # days inventory outstanding
    dpo_days: int = 40                            # days payables outstanding
    tax_rate_pct: float = 25.0
    wacc_pct: float = 9.0
    terminal_growth_pct: float = 2.0
    exit_multiple_ev_ebitda: float = 8.0


@dataclass(frozen=True)
class Sector:
    id: str
    label: str
    group: str
    description: str
    key_kpis: List[str]                            # surfaced in dashboards
    defaults: SectorDefaults
    # Optional: line-item keywords specific to this sector. Used by the
    # auto-seed pattern matcher to recognise sector-specific accounts (e.g.
    # SaaS expects "ARR" or "MRR"; Real Estate expects "NOI").
    line_item_hints: Dict[str, List[str]] = field(default_factory=dict)


# Order within a group is intentional: the most common pick first so the
# default scroll position lands on a sensible option.
SECTORS: List[Sector] = [
    # ── Technology ──────────────────────────────────────────────────────────
    Sector(
        id="saas",
        label="SaaS / Software",
        group="Technology",
        description="Recurring-revenue software (ARR/MRR-driven). High gross margin, heavy S&M spend.",
        key_kpis=["ARR", "Net Revenue Retention", "Gross Margin", "Rule of 40"],
        defaults=SectorDefaults(
            revenue_growth_pct=20, gross_margin_pct=75, opex_pct_of_revenue=55,
            da_pct_of_revenue=3, capex_pct_of_revenue=3,
            dso_days=40, dio_days=0, dpo_days=30,
            tax_rate_pct=21, wacc_pct=11, terminal_growth_pct=3, exit_multiple_ev_ebitda=15,
        ),
        line_item_hints={"revenue": ["arr", "mrr", "subscription", "subscriptions"]},
    ),
    Sector(
        id="ecommerce",
        label="E-commerce / Marketplace",
        group="Technology",
        description="Online retail / marketplace. Volume + take-rate driven, working capital sensitive.",
        key_kpis=["GMV", "Take Rate", "CAC Payback", "Contribution Margin"],
        defaults=SectorDefaults(
            revenue_growth_pct=15, gross_margin_pct=35, opex_pct_of_revenue=28,
            da_pct_of_revenue=3, capex_pct_of_revenue=3,
            dso_days=20, dio_days=45, dpo_days=50,
            tax_rate_pct=25, wacc_pct=10, terminal_growth_pct=2.5, exit_multiple_ev_ebitda=12,
        ),
    ),

    # ── Consumer ────────────────────────────────────────────────────────────
    Sector(
        id="retail",
        label="Retail",
        group="Consumer",
        description="Brick-and-mortar or omnichannel retail. Same-store sales + new store rollout.",
        key_kpis=["Same-Store Sales Growth", "Store Count", "Sales / sq ft", "Inventory Turns"],
        defaults=SectorDefaults(
            revenue_growth_pct=4, gross_margin_pct=40, opex_pct_of_revenue=32,
            da_pct_of_revenue=3, capex_pct_of_revenue=4,
            dso_days=10, dio_days=60, dpo_days=45,
            tax_rate_pct=25, wacc_pct=8, terminal_growth_pct=2, exit_multiple_ev_ebitda=8,
        ),
    ),
    Sector(
        id="cpg",
        label="Consumer Goods (CPG)",
        group="Consumer",
        description="Branded consumer products. Stable margins, advertising-heavy.",
        key_kpis=["Volume Growth", "Price/Mix", "Gross Margin", "A&P % Sales"],
        defaults=SectorDefaults(
            revenue_growth_pct=3, gross_margin_pct=45, opex_pct_of_revenue=30,
            da_pct_of_revenue=3, capex_pct_of_revenue=3,
            dso_days=40, dio_days=70, dpo_days=55,
            tax_rate_pct=25, wacc_pct=7, terminal_growth_pct=2, exit_multiple_ev_ebitda=12,
        ),
    ),

    # ── Industrial / Materials ──────────────────────────────────────────────
    Sector(
        id="industrial",
        label="Industrial / Manufacturing",
        group="Industrial",
        description="Capital-intensive manufacturing. Capacity utilisation + cycle exposure.",
        key_kpis=["Capacity Utilisation", "EBITDA Margin", "Capex / Sales", "Order Backlog"],
        defaults=SectorDefaults(
            revenue_growth_pct=4, gross_margin_pct=28, opex_pct_of_revenue=15,
            da_pct_of_revenue=6, capex_pct_of_revenue=7,
            dso_days=60, dio_days=80, dpo_days=55,
            tax_rate_pct=25, wacc_pct=8, terminal_growth_pct=2, exit_multiple_ev_ebitda=8,
        ),
    ),
    Sector(
        id="energy",
        label="Energy / Utilities",
        group="Industrial",
        description="Power generation, oil & gas, regulated utilities. Long-asset, regulated returns.",
        key_kpis=["Production Volume", "Realised Price", "Reserves", "Reg. RoE"],
        defaults=SectorDefaults(
            revenue_growth_pct=2, gross_margin_pct=35, opex_pct_of_revenue=15,
            da_pct_of_revenue=10, capex_pct_of_revenue=12,
            dso_days=45, dio_days=20, dpo_days=40,
            tax_rate_pct=28, wacc_pct=7, terminal_growth_pct=1.5, exit_multiple_ev_ebitda=7,
        ),
    ),

    # ── Real Estate / Infra ────────────────────────────────────────────────
    Sector(
        id="real_estate",
        label="Real Estate",
        group="Real Estate & Infra",
        description="Income-producing property (NOI-driven). Cap-rate valuation context.",
        key_kpis=["NOI", "Occupancy", "Cap Rate", "Same-Store NOI Growth"],
        defaults=SectorDefaults(
            revenue_growth_pct=3, gross_margin_pct=65, opex_pct_of_revenue=10,
            da_pct_of_revenue=15, capex_pct_of_revenue=8,
            dso_days=15, dio_days=0, dpo_days=15,
            tax_rate_pct=25, wacc_pct=6, terminal_growth_pct=2, exit_multiple_ev_ebitda=18,
        ),
        line_item_hints={"revenue": ["rental income", "noi", "rents"]},
    ),
    Sector(
        id="project_finance",
        label="Project Finance / Infra",
        group="Real Estate & Infra",
        description="Single-asset infrastructure (toll roads, renewables, PPP). DSCR-driven.",
        key_kpis=["DSCR", "Equity IRR", "P50 Output", "Lifetime"],
        defaults=SectorDefaults(
            revenue_growth_pct=2, gross_margin_pct=70, opex_pct_of_revenue=15,
            da_pct_of_revenue=20, capex_pct_of_revenue=2,
            dso_days=45, dio_days=10, dpo_days=30,
            tax_rate_pct=25, wacc_pct=7, terminal_growth_pct=0, exit_multiple_ev_ebitda=10,
        ),
    ),

    # ── Healthcare ─────────────────────────────────────────────────────────
    Sector(
        id="healthcare_services",
        label="Healthcare Services",
        group="Healthcare",
        description="Hospitals, clinics, providers. Volume + reimbursement driven.",
        key_kpis=["Patient Volume", "Avg Revenue/Visit", "Payer Mix", "EBITDA Margin"],
        defaults=SectorDefaults(
            revenue_growth_pct=5, gross_margin_pct=30, opex_pct_of_revenue=18,
            da_pct_of_revenue=4, capex_pct_of_revenue=5,
            dso_days=55, dio_days=20, dpo_days=40,
            tax_rate_pct=25, wacc_pct=8, terminal_growth_pct=2.5, exit_multiple_ev_ebitda=10,
        ),
    ),
    Sector(
        id="biotech_pharma",
        label="Biotech / Pharma",
        group="Healthcare",
        description="Drug development & manufacturing. R&D heavy, patent cliffs, regulatory binary.",
        key_kpis=["Pipeline Value", "Peak Sales", "R&D % Sales", "Patent Coverage"],
        defaults=SectorDefaults(
            revenue_growth_pct=6, gross_margin_pct=75, opex_pct_of_revenue=45,
            da_pct_of_revenue=4, capex_pct_of_revenue=5,
            dso_days=60, dio_days=80, dpo_days=50,
            tax_rate_pct=20, wacc_pct=10, terminal_growth_pct=2, exit_multiple_ev_ebitda=14,
        ),
    ),

    # ── Financials ─────────────────────────────────────────────────────────
    Sector(
        id="banking",
        label="Banking",
        group="Financials",
        description="Commercial / retail banking. NIM, loan book growth, capital ratios.",
        key_kpis=["NIM", "Loan Growth", "Cost/Income", "RoTE", "CET1"],
        defaults=SectorDefaults(
            revenue_growth_pct=4, gross_margin_pct=None, opex_pct_of_revenue=55,
            da_pct_of_revenue=2, capex_pct_of_revenue=2,
            dso_days=0, dio_days=0, dpo_days=0,
            tax_rate_pct=25, wacc_pct=10, terminal_growth_pct=2.5, exit_multiple_ev_ebitda=9,
        ),
    ),
    Sector(
        id="insurance",
        label="Insurance",
        group="Financials",
        description="P&C / life insurance. Combined ratio + investment yield.",
        key_kpis=["Combined Ratio", "Loss Ratio", "Premium Growth", "Investment Yield"],
        defaults=SectorDefaults(
            revenue_growth_pct=4, gross_margin_pct=None, opex_pct_of_revenue=30,
            da_pct_of_revenue=2, capex_pct_of_revenue=2,
            dso_days=30, dio_days=0, dpo_days=0,
            tax_rate_pct=25, wacc_pct=8, terminal_growth_pct=2, exit_multiple_ev_ebitda=8,
        ),
    ),

    # ── Generic fallback ───────────────────────────────────────────────────
    Sector(
        id="generic",
        label="Other / Generic",
        group="Other",
        description="No specific sector — uses neutral defaults. You can refine later.",
        key_kpis=["Revenue", "EBITDA Margin", "Free Cash Flow"],
        defaults=SectorDefaults(revenue_growth_pct=5),
    ),
]


SECTOR_BY_ID: Dict[str, Sector] = {s.id: s for s in SECTORS}


def get_sector(sector_id: Optional[str]) -> Sector:
    """Return the sector for an id, falling back to 'generic' for unknown/None.

    We never raise here: a project created before this catalog existed has
    `sector=NULL` and should still get a sensible auto-seed.
    """
    if not sector_id:
        return SECTOR_BY_ID["generic"]
    return SECTOR_BY_ID.get(sector_id, SECTOR_BY_ID["generic"])


def list_sectors_grouped() -> List[Dict]:
    """Catalog formatted for the UI sector picker (grouped by `group`)."""
    by_group: Dict[str, List[Dict]] = {}
    for s in SECTORS:
        by_group.setdefault(s.group, []).append({
            "id": s.id,
            "label": s.label,
            "description": s.description,
            "key_kpis": s.key_kpis,
        })
    return [{"group": g, "sectors": items} for g, items in by_group.items()]
