"""Pydantic schemas for user AI settings."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class AISettingsUpdate(BaseModel):
    """Payload for PUT /me/ai-settings."""
    provider: Literal["google", "anthropic", "openai"] = "google"
    api_key: str = Field(..., min_length=1, description="Plain-text API key (will be encrypted)")
    cheap_model: str = Field(default="gemini-2.5-flash", max_length=100)
    smart_model: str = Field(default="gemini-2.5-pro", max_length=100)


class AISettingsOut(BaseModel):
    """Response for GET /me/ai-settings.  Key is masked."""
    provider: str
    api_key_masked: str
    cheap_model: str
    smart_model: str
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class AISettingsTestResult(BaseModel):
    """Response for POST /me/ai-settings/test."""
    success: bool
    model: str
    message: str
    latency_ms: Optional[float] = None
