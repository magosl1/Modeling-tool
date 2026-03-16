"""Pydantic schemas for Entity model."""
from pydantic import BaseModel, field_validator
from typing import Optional, List, Any


class EntityCreate(BaseModel):
    name: str
    entity_type: str = "company_private"
    currency: str = "EUR"
    country: Optional[str] = None
    sector: Optional[str] = None
    description: Optional[str] = None
    ticker: Optional[str] = None
    exchange: Optional[str] = None
    ownership_pct: float = 100.0
    consolidation_method: str = "full"
    parent_entity_id: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    display_order: int = 0

    @field_validator("entity_type")
    @classmethod
    def validate_entity_type(cls, v: str) -> str:
        allowed = {"company_listed", "company_private", "project", "division", "asset", "holdco"}
        if v not in allowed:
            raise ValueError(f"entity_type must be one of {allowed}")
        return v

    @field_validator("consolidation_method")
    @classmethod
    def validate_consolidation_method(cls, v: str) -> str:
        allowed = {"full", "proportional", "equity_method", "none"}
        if v not in allowed:
            raise ValueError(f"consolidation_method must be one of {allowed}")
        return v

    @field_validator("ownership_pct")
    @classmethod
    def validate_ownership(cls, v: float) -> float:
        if v < 0 or v > 100:
            raise ValueError("ownership_pct must be between 0 and 100")
        return v


class EntityUpdate(BaseModel):
    name: Optional[str] = None
    entity_type: Optional[str] = None
    currency: Optional[str] = None
    country: Optional[str] = None
    sector: Optional[str] = None
    description: Optional[str] = None
    ticker: Optional[str] = None
    exchange: Optional[str] = None
    ownership_pct: Optional[float] = None
    consolidation_method: Optional[str] = None
    parent_entity_id: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    is_active: Optional[bool] = None
    display_order: Optional[int] = None


class EntityOut(BaseModel):
    id: str
    project_id: str
    parent_entity_id: Optional[str]
    name: str
    entity_type: str
    ticker: Optional[str]
    exchange: Optional[str]
    currency: str
    country: Optional[str]
    sector: Optional[str]
    description: Optional[str]
    ownership_pct: float
    consolidation_method: str
    is_active: bool
    start_date: Optional[str]
    end_date: Optional[str]
    display_order: int
    created_at: Any
    updated_at: Any

    model_config = {"from_attributes": True}


class BulkCreateRequest(BaseModel):
    template: EntityCreate
    count: int
    naming_pattern: str = "{name} {n}"

    @field_validator("count")
    @classmethod
    def validate_count(cls, v: int) -> int:
        if v < 1 or v > 200:
            raise ValueError("count must be between 1 and 200")
        return v


class CloneEntityRequest(BaseModel):
    new_name: str
    overrides: Optional[dict] = None
