"""Unified LLM client for AI ingestion pipeline.

Provides two public functions:
    - ``cheap_complete(user_id, messages, ...)`` — fast/cheap model
    - ``smart_complete(user_id, messages, ...)`` — powerful model for complex cases

Uses LiteLLM under the hood. API keys are decrypted from the user's
``UserAISettings`` at call time — never cached in memory.

The LLM **never** sees raw numbers. Callers send only labels and structure.
"""
from __future__ import annotations

import json
import time
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.encryption import decrypt_api_key
from app.core.logging import get_logger
from app.models.ai_settings import UserAISettings

log = get_logger("app.llm")


# ---------------------------------------------------------------------------
# Custom error types
# ---------------------------------------------------------------------------

class LLMError(Exception):
    """Base class for LLM-related errors."""
    http_status: int = 500


class LLMNoKeyError(LLMError):
    """User has not configured an API key."""
    http_status: int = 400

    def __init__(self) -> None:
        super().__init__(
            "AI settings not configured. "
            "Go to Settings → AI and add your API key before using AI features."
        )


class LLMRateLimitError(LLMError):
    """Upstream rate limit exceeded."""
    http_status: int = 429

    def __init__(self, retry_after: Optional[float] = None) -> None:
        msg = "AI provider rate limit exceeded. Please wait a moment and try again."
        if retry_after:
            msg += f" (retry after {retry_after:.0f}s)"
        super().__init__(msg)
        self.retry_after = retry_after


class LLMTimeoutError(LLMError):
    """LLM call timed out."""
    http_status: int = 504

    def __init__(self, timeout_s: float) -> None:
        super().__init__(f"AI model did not respond within {timeout_s:.0f}s. Try again or use a faster model.")
        self.timeout_s = timeout_s


class LLMSchemaError(LLMError):
    """LLM returned an invalid/unparseable response."""
    http_status: int = 502

    def __init__(self, detail: str = "") -> None:
        msg = "AI model returned an invalid response."
        if detail:
            msg += f" Detail: {detail}"
        super().__init__(msg)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_user_settings(user_id: str, db: Session) -> UserAISettings:
    """Fetch user AI settings or raise ``LLMNoKeyError``."""
    row = db.query(UserAISettings).filter(UserAISettings.user_id == user_id).first()
    if not row:
        raise LLMNoKeyError()
    return row


def _litellm_model_name(provider: str, model: str) -> str:
    """Build the model identifier that LiteLLM expects."""
    if provider == "google":
        return f"gemini/{model}"
    if provider == "anthropic":
        return f"anthropic/{model}"
    # OpenAI models don't need a prefix in litellm.
    return model


def _call_litellm(
    *,
    model: str,
    api_key: str,
    messages: list[dict[str, Any]],
    tools: Optional[list[dict[str, Any]]] = None,
    tool_choice: Optional[str | dict[str, Any]] = None,
    response_format: Optional[dict[str, Any] | Any] = None,
    timeout: float,
    max_tokens: int = 4096,
    temperature: float = 0.0,
    fallback_model: Optional[str] = None,
    max_retries: int = 3,
) -> dict[str, Any]:
    """Low-level wrapper around ``litellm.completion``.

    Translates upstream exceptions into our typed errors.
    """
    import litellm

    kwargs: dict[str, Any] = {
        "model": model,
        "api_key": api_key,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "timeout": timeout,
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = tool_choice or "auto"
    if response_format:
        # Gemini/VertexAI is extremely strict and fails if "additionalProperties" is present in nested objects
        if model.startswith("gemini/"):
            schema = None
            if hasattr(response_format, "model_json_schema"):
                schema = response_format.model_json_schema()
            elif isinstance(response_format, dict):
                schema = response_format

            if schema:
                def strip_additional_props(obj):
                    if isinstance(obj, dict):
                        obj.pop("additionalProperties", None)
                        # Vertex AI also doesn't like 'titles' or 'descriptions' sometimes in nested schemas if strict
                        for k in list(obj.keys()):
                            if k in ["title", "description"]:
                                obj.pop(k)
                        for v in obj.values():
                            strip_additional_props(v)
                    elif isinstance(obj, list):
                        for v in obj:
                            strip_additional_props(v)
                
                import copy
                schema_clean = copy.deepcopy(schema)
                strip_additional_props(schema_clean)
                log.info(f"Using cleaned schema for Gemini: {json.dumps(schema_clean)[:200]}...")
                kwargs["response_format"] = {"type": "json_schema", "json_schema": {"schema": schema_clean}}
            else:
                kwargs["response_format"] = response_format
        else:
            kwargs["response_format"] = response_format

    start = time.perf_counter()
    last_exc: Exception | None = None

    # Try primary model with retries, then fallback model once
    models_to_try = [model]
    if fallback_model and fallback_model != model:
        models_to_try.append(fallback_model)

    for attempt_model in models_to_try:
        kwargs["model"] = attempt_model
        # Rebuild safety settings for the actual model being tried
        if attempt_model.startswith("gemini/"):
            kwargs["safety_settings"] = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ]
        else:
            kwargs.pop("safety_settings", None)

        for attempt in range(max_retries):
            try:
                response = litellm.completion(**kwargs)
                last_exc = None
                break  # success
            except litellm.RateLimitError:
                raise LLMRateLimitError()
            except litellm.Timeout:
                raise LLMTimeoutError(timeout)
            except litellm.APIConnectionError as exc:
                raise LLMError(f"Cannot reach AI provider: {exc}") from exc
            except litellm.AuthenticationError:
                raise LLMError(
                    "API key rejected by the AI provider. "
                    "Check your key in Settings → AI."
                )
            except Exception as exc:
                err_str = str(exc)
                is_503 = "503" in err_str or "UNAVAILABLE" in err_str or "ServiceUnavailable" in err_str
                if is_503 and attempt < max_retries - 1:
                    wait = 5 * (attempt + 1)  # 5s, 10s, 15s
                    log.warning(
                        "llm_503_retry",
                        model=attempt_model,
                        attempt=attempt + 1,
                        wait_s=wait,
                    )
                    time.sleep(wait)
                    last_exc = exc
                    continue
                last_exc = exc
                break  # try fallback

        if last_exc is None:
            break  # got a response, stop trying models
        log.warning("llm_model_failed", model=attempt_model, error=str(last_exc))

    if last_exc is not None:
        raise LLMError(f"Unexpected LLM error: {last_exc}") from last_exc

    latency_ms = (time.perf_counter() - start) * 1000

    # Extract usage stats for logging.
    usage = getattr(response, "usage", None)
    tokens_in = getattr(usage, "prompt_tokens", 0) if usage else 0
    tokens_out = getattr(usage, "completion_tokens", 0) if usage else 0

    log.info(
        "llm_call",
        model=model,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        latency_ms=round(latency_ms, 1),
    )

    # Normalize to dict.
    return response.model_dump() if hasattr(response, "model_dump") else dict(response)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_CHEAP_TIMEOUT = 60.0   # seconds
_SMART_TIMEOUT = 120.0  # seconds


def cheap_complete(
    user_id: str,
    db: Session,
    messages: list[dict[str, Any]],
    *,
    tools: Optional[list[dict[str, Any]]] = None,
    tool_choice: Optional[str | dict[str, Any]] = None,
    response_format: Optional[dict[str, Any]] = None,
    max_tokens: int = 4096,
) -> dict[str, Any]:
    """Call the user's configured *cheap* (fast) model.

    Intended for straightforward documents where a lightweight model suffices.
    """
    settings = _get_user_settings(user_id, db)
    api_key = decrypt_api_key(settings.api_key_encrypted)
    model = _litellm_model_name(settings.provider, settings.cheap_model)

    return _call_litellm(
        model=model,
        api_key=api_key,
        messages=messages,
        tools=tools,
        tool_choice=tool_choice,
        response_format=response_format,
        timeout=_CHEAP_TIMEOUT,
        max_tokens=max_tokens,
    )


def smart_complete(
    user_id: str,
    db: Session,
    messages: list[dict[str, Any]],
    *,
    tools: Optional[list[dict[str, Any]]] = None,
    tool_choice: Optional[str | dict[str, Any]] = None,
    response_format: Optional[dict[str, Any] | Any] = None,
    max_tokens: int = 16384,
) -> dict[str, Any]:
    """Call the user's configured *smart* (powerful) model.

    Used for complex documents: long PDFs, messy Excel layouts, etc.
    """
    settings = _get_user_settings(user_id, db)
    api_key = decrypt_api_key(settings.api_key_encrypted)
    model = _litellm_model_name(settings.provider, settings.smart_model)
    # Use cheap model as automatic fallback if smart model is unavailable (e.g. Gemini 503)
    fallback_model = _litellm_model_name(settings.provider, settings.cheap_model)

    return _call_litellm(
        model=model,
        fallback_model=fallback_model,
        api_key=api_key,
        messages=messages,
        tools=tools,
        tool_choice=tool_choice,
        response_format=response_format,
        timeout=_SMART_TIMEOUT,
        max_tokens=max_tokens,
    )


def extract_content(response: dict[str, Any]) -> str:
    """Extract the text content from a litellm response dict."""
    choices = response.get("choices", [])
    if not choices:
        raise LLMSchemaError("No choices in response")
    message = choices[0].get("message", {})
    return message.get("content", "") or ""


def extract_tool_calls(response: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract tool call arguments from a litellm response dict."""
    choices = response.get("choices", [])
    if not choices:
        raise LLMSchemaError("No choices in response")
    message = choices[0].get("message", {})
    tool_calls = message.get("tool_calls")
    if not tool_calls:
        raise LLMSchemaError("Model did not use the requested tool")
    return tool_calls
