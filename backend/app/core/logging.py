"""Structured logging setup using structlog.

In DEBUG mode we render colored, human-friendly logs. In production we emit
JSON lines so log aggregators can parse them. Structlog is configured once
at import time (idempotent — calling configure_logging() multiple times is
safe).
"""
import logging
import sys

import structlog

from app.core.config import settings

_configured = False


def configure_logging() -> None:
    global _configured
    if _configured:
        return

    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        timestamper,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.DEBUG:
        renderer = structlog.dev.ConsoleRenderer(colors=False)
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=shared_processors + [renderer],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Quiet down noisy third-party loggers in production.
    if not settings.DEBUG:
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    _configured = True


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    configure_logging()
    return structlog.get_logger(name)
