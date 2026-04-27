"""Routes for user AI settings management.

Endpoints:
    GET    /me/ai-settings       — retrieve (masked key)
    PUT    /me/ai-settings       — create or update
    DELETE /me/ai-settings       — remove
    POST   /me/ai-settings/test  — validate key with a trivial LLM call
"""
from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.encryption import decrypt_api_key, encrypt_api_key, mask_api_key
from app.db.base import get_db
from app.models.ai_settings import UserAISettings
from app.models.user import User
from app.schemas.ai_settings import AISettingsOut, AISettingsTestResult, AISettingsUpdate

router = APIRouter(prefix="/me", tags=["ai-settings"])


@router.get("/ai-settings", response_model=AISettingsOut)
def get_ai_settings(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = db.query(UserAISettings).filter(UserAISettings.user_id == user.id).first()
    if not row:
        raise HTTPException(status_code=404, detail="AI settings not configured")
    plain_key = decrypt_api_key(row.api_key_encrypted)
    return AISettingsOut(
        provider=row.provider,
        api_key_masked=mask_api_key(plain_key),
        cheap_model=row.cheap_model,
        smart_model=row.smart_model,
        created_at=row.created_at.isoformat(),
        updated_at=row.updated_at.isoformat(),
    )


@router.put("/ai-settings", response_model=AISettingsOut)
def upsert_ai_settings(
    data: AISettingsUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = db.query(UserAISettings).filter(UserAISettings.user_id == user.id).first()
    key_changed = data.api_key != "___UNCHANGED___"

    if row:
        row.provider = data.provider
        if key_changed:
            row.api_key_encrypted = encrypt_api_key(data.api_key)
        row.cheap_model = data.cheap_model
        row.smart_model = data.smart_model
    else:
        if not key_changed:
            raise HTTPException(status_code=400, detail="API key is required for initial setup")
        row = UserAISettings(
            user_id=user.id,
            provider=data.provider,
            api_key_encrypted=encrypt_api_key(data.api_key),
            cheap_model=data.cheap_model,
            smart_model=data.smart_model,
        )
        db.add(row)
    db.commit()
    db.refresh(row)
    display_key = data.api_key if key_changed else decrypt_api_key(row.api_key_encrypted)
    return AISettingsOut(
        provider=row.provider,
        api_key_masked=mask_api_key(display_key),
        cheap_model=row.cheap_model,
        smart_model=row.smart_model,
        created_at=row.created_at.isoformat(),
        updated_at=row.updated_at.isoformat(),
    )


@router.delete("/ai-settings", status_code=status.HTTP_204_NO_CONTENT)
def delete_ai_settings(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = db.query(UserAISettings).filter(UserAISettings.user_id == user.id).first()
    if not row:
        raise HTTPException(status_code=404, detail="AI settings not configured")
    db.delete(row)
    db.commit()


@router.post("/ai-settings/test", response_model=AISettingsTestResult)
def test_ai_settings(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Make a trivial call to the cheap model to validate the API key."""
    row = db.query(UserAISettings).filter(UserAISettings.user_id == user.id).first()
    if not row:
        raise HTTPException(status_code=404, detail="AI settings not configured. Save your key first.")

    model = row.cheap_model
    start = time.perf_counter()
    try:
        from app.services.llm_client import cheap_complete, extract_content
        response = cheap_complete(
            user.id, db,
            [{"role": "user", "content": "Reply with exactly: OK"}],
            max_tokens=5,
        )
        latency_ms = (time.perf_counter() - start) * 1000
        content = extract_content(response).strip()
        return AISettingsTestResult(
            success=True,
            model=model,
            message=f"✅ Conectado a {model} — respuesta: \"{content}\"",
            latency_ms=round(latency_ms, 1),
        )
    except Exception as exc:
        latency_ms = (time.perf_counter() - start) * 1000
        error_msg = str(exc)
        if len(error_msg) > 300:
            error_msg = error_msg[:300] + "…"
        return AISettingsTestResult(
            success=False,
            model=model,
            message=f"❌ Error: {error_msg}",
            latency_ms=round(latency_ms, 1),
        )

