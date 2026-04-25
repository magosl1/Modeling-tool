"""Projection engine — 21-step compile, split by domain.

Public surface: `ProjectionEngine` and `ProjectionResult`.
"""
from app.services.projections._state import ProjectionResult
from app.services.projections.engine import ProjectionEngine

__all__ = ["ProjectionEngine", "ProjectionResult"]
