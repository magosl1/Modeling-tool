"""Audit service — write-only helper for the global change log.

Usage:
    from app.services.audit_service import log_change, serialize_model

    # Before modifying the DB row:
    before = serialize_model(assumption)
    # … make changes …
    db.flush()
    after = serialize_model(assumption)
    log_change(db, project_id=..., user_id=...,
               entity="assumption", entity_id=assumption.id,
               action="update", before=before, after=after,
               summary="Revenue · growth_rate: 8.0% → 10.0%")
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import uuid

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.audit import ChangeLog

log = get_logger("app.services.audit")


def serialize_model(obj: Any) -> dict:
    """Convert a SQLAlchemy model instance to a JSON-safe dict."""
    if obj is None:
        return {}
    try:
        return jsonable_encoder(obj, exclude={"project", "entity", "params", "assumption"})
    except Exception:
        # Fallback: use __dict__ minus private SQLAlchemy keys
        return {k: v for k, v in vars(obj).items() if not k.startswith("_")}


def build_summary(entity: str, action: str, before: dict, after: dict) -> str:
    """Generate a short human-readable description of what changed."""
    if action == "create":
        name = after.get("line_item") or after.get("name") or after.get("statement_type", "")
        return f"{entity.capitalize()} created: {name}"
    if action == "delete":
        name = before.get("line_item") or before.get("name") or before.get("statement_type", "")
        return f"{entity.capitalize()} deleted: {name}"
    # update — find the first changed scalar key
    changed = []
    all_keys = set(before.keys()) | set(after.keys())
    for k in sorted(all_keys):
        bv = before.get(k)
        av = after.get(k)
        if bv != av and not isinstance(av, (dict, list)):
            changed.append(f"{k}: {bv} → {av}")
    if changed:
        label = after.get("line_item") or after.get("name") or entity
        return f"{label} · " + ", ".join(changed[:2])
    return f"{entity.capitalize()} updated"


def log_change(
    db: Session,
    *,
    project_id: str,
    user_id: str | None,
    entity: str,
    entity_id: str,
    action: str,
    before: dict | None = None,
    after: dict | None = None,
    summary: str | None = None,
) -> None:
    """Append one immutable row to change_log. Never raises — audit must not break the main flow."""
    try:
        if summary is None:
            summary = build_summary(entity, action, before or {}, after or {})
        entry = ChangeLog(
            id=str(uuid.uuid4()),
            project_id=project_id,
            user_id=user_id,
            entity=entity,
            entity_id=entity_id,
            action=action,
            summary=summary,
            before_json=before,
            after_json=after,
            created_at=datetime.now(timezone.utc),
        )
        db.add(entry)
        # We intentionally do NOT commit here — let the caller's transaction commit both
        # the business change and this log entry atomically.
    except Exception as exc:
        log.warning("audit_log_failed", error=str(exc), entity=entity, entity_id=entity_id)
