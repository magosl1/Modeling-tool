from pydantic import BaseModel, field_validator
from typing import Optional, List, Any
from datetime import date
from decimal import Decimal


class ProjectCreate(BaseModel):
    name: str
    currency: str = "USD"
    scale: str = "thousands"
    fiscal_year_end: Optional[date] = None
    projection_years: int = 5


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    currency: Optional[str] = None
    scale: Optional[str] = None
    fiscal_year_end: Optional[date] = None
    projection_years: Optional[int] = None


class ProjectOut(BaseModel):
    id: str
    name: str
    currency: str
    scale: str
    fiscal_year_end: Optional[date]
    projection_years: int
    status: str
    created_at: Any
    updated_at: Any

    model_config = {"from_attributes": True}


class HistoricalDataPoint(BaseModel):
    statement_type: str
    line_item: str
    bucket: Optional[str] = None
    year: int
    value: Decimal


class ValidationError(BaseModel):
    tab: str
    line_item: str
    year: int
    error_message: str


class ValidationResult(BaseModel):
    valid: bool
    errors: List[ValidationError] = []


class RevenueStreamCreate(BaseModel):
    stream_name: str
    display_order: int = 0
    projection_method: str


class RevenueStreamParamCreate(BaseModel):
    param_key: str
    year: Optional[int] = None
    value: Decimal


class AssumptionCreate(BaseModel):
    line_item: str
    projection_method: str
    params: List[dict] = []


class ModuleAssumptionSave(BaseModel):
    module: str
    assumptions: List[AssumptionCreate]


class ModuleStatus(BaseModel):
    module: str
    status: str  # not_started | configured | complete | error
    message: Optional[str] = None


class ValuationInputCreate(BaseModel):
    wacc: Decimal
    terminal_growth_rate: Decimal
    exit_multiple: Optional[Decimal] = None
    discounting_convention: str = "end_of_year"
    shares_outstanding: Optional[Decimal] = None

    @field_validator("wacc")
    @classmethod
    def wacc_range(cls, v: Decimal) -> Decimal:
        if v <= 0 or v > 50:
            raise ValueError("WACC must be between 0 and 50 (%)")
        return v

    @field_validator("terminal_growth_rate")
    @classmethod
    def growth_rate_range(cls, v: Decimal) -> Decimal:
        if v < -5 or v > 20:
            raise ValueError("Terminal growth rate must be between -5 and 20 (%)")
        return v


class ValuationOutputOut(BaseModel):
    enterprise_value: Decimal
    net_debt: Decimal
    equity_value: Decimal
    value_per_share: Optional[Decimal]
    terminal_value: Decimal
    pv_fcffs: Decimal
    pv_terminal_value: Decimal
    method_used: str
    fcff_by_year: dict
    sensitivity_table: dict

    model_config = {"from_attributes": True}


class ProjectedFinancialOut(BaseModel):
    statement_type: str
    line_item: str
    year: int
    value: Decimal

    model_config = {"from_attributes": True}
