"""Backwards-compatible shim — the engine now lives in `app.services.projections`.

Kept so existing `from app.services.projection_engine import ProjectionEngine`
callers don't break. New code should import from `app.services.projections`.
"""
from app.services.projections import ProjectionEngine, ProjectionResult

__all__ = ["ProjectionEngine", "ProjectionResult"]
