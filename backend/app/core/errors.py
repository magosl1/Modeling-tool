"""Global exception handlers + uniform error response schema.

Every error response uses the shape:

    {
        "error": {
            "code": "<machine-readable code>",
            "message": "<human-readable message>",
            "request_id": "<correlation id>",
            "details": {...}            # optional, only when relevant
        }
    }

Handlers registered:
- HTTPException                → preserves status + detail, normalizes shape
- RequestValidationError (422) → exposes which fields failed
- Exception (catch-all 500)    → logs with stack trace, hides internals from client
"""
from __future__ import annotations

import uuid
from typing import Any

import structlog
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logging import get_logger

log = get_logger("app.errors")


def _payload(
    code: str,
    message: str,
    request_id: str,
    details: Any = None,
) -> dict:
    body: dict[str, Any] = {"code": code, "message": message, "request_id": request_id}
    if details is not None:
        body["details"] = details
    return {"error": body}


def _request_id(request: Request) -> str:
    rid = getattr(request.state, "request_id", None)
    return rid or "unknown"


def _with_rid_header(response: JSONResponse, rid: str) -> JSONResponse:
    response.headers["x-request-id"] = rid
    return response


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    rid = _request_id(request)
    headers = dict(getattr(exc, "headers", None) or {})
    response = JSONResponse(
        status_code=exc.status_code,
        content=_payload(
            code=f"http_{exc.status_code}",
            message=str(exc.detail) if exc.detail else "Request failed",
            request_id=rid,
        ),
        headers=headers,
    )
    return _with_rid_header(response, rid)


from fastapi.encoders import jsonable_encoder

async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    rid = _request_id(request)
    response = JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=_payload(
            code="validation_error",
            message="Request validation failed",
            request_id=rid,
            details={"errors": jsonable_encoder(exc.errors())},
        ),
    )
    return _with_rid_header(response, rid)


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    rid = _request_id(request)
    log.error(
        "unhandled_exception",
        request_id=rid,
        path=request.url.path,
        method=request.method,
        exc_info=exc,
    )
    response = JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_payload(
            code="internal_error",
            message="An internal error occurred. Please try again later.",
            request_id=rid,
        ),
    )
    return _with_rid_header(response, rid)


def install_exception_handlers(app: FastAPI) -> None:
    from app.services.document_extractor import ExtractionError
    from app.services.llm_client import LLMError

    async def llm_exception_handler(request: Request, exc: LLMError) -> JSONResponse:
        rid = _request_id(request)
        response = JSONResponse(
            status_code=exc.http_status,
            content=_payload(
                code="llm_error",
                message=str(exc),
                request_id=rid,
            ),
        )
        return _with_rid_header(response, rid)

    async def extraction_exception_handler(request: Request, exc: ExtractionError) -> JSONResponse:
        rid = _request_id(request)
        response = JSONResponse(
            status_code=exc.http_status,
            content=_payload(
                code="extraction_error",
                message=str(exc),
                request_id=rid,
            ),
        )
        return _with_rid_header(response, rid)

    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(LLMError, llm_exception_handler)
    app.add_exception_handler(ExtractionError, extraction_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)


async def request_id_middleware(request: Request, call_next):
    """Attach a unique request_id (incoming X-Request-ID header or new UUID).

    Bind it into structlog's contextvars so any log emitted during the request
    is automatically tagged with the same id.
    """
    incoming = request.headers.get("x-request-id")
    rid = incoming or uuid.uuid4().hex
    request.state.request_id = rid
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=rid)
    response = await call_next(request)
    response.headers["x-request-id"] = rid
    return response
