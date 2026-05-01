import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    admin,
    ai_settings,
    assumptions,
    auth,
    consolidated,
    curves,
    debt,
    entities,
    fx,
    historical,
    metadata,
    projections,
    projects,
    ratios,
    revenue_streams,
    scenarios,
    sharing,
    simulation,
    templates,
    valuation,
)
from app.core.config import settings
from app.core.errors import install_exception_handlers, request_id_middleware
from app.core.logging import get_logger

log = get_logger("app.access")

app = FastAPI(
    title=settings.APP_NAME,
    description="Financial Modeling Platform — MVP",
    version="1.0.0",
)

install_exception_handlers(app)
app.middleware("http")(request_id_middleware)


from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.rate_limit import limiter

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000
    log.info(
        "request",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=round(elapsed_ms, 1),
    )
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)

# Auth
app.include_router(auth.router, prefix=settings.API_V1_STR)

# Projects
app.include_router(projects.router, prefix=settings.API_V1_STR)

# Historical data + templates
app.include_router(historical.router, prefix=settings.API_V1_STR)
app.include_router(templates.router, prefix=settings.API_V1_STR)

# Assumptions
app.include_router(assumptions.router, prefix=settings.API_V1_STR)

# Projections
app.include_router(projections.router, prefix=settings.API_V1_STR)

# Valuation
app.include_router(valuation.router, prefix=settings.API_V1_STR)

# Ratios
app.include_router(ratios.router, prefix=settings.API_V1_STR)

# Metadata
app.include_router(metadata.router, prefix=settings.API_V1_STR)

# Scenarios
app.include_router(scenarios.router, prefix=settings.API_V1_STR)

# Debt schedule (Block 2)
app.include_router(debt.router, prefix=settings.API_V1_STR)

# FX rates (Block 3)
app.include_router(fx.router, prefix=settings.API_V1_STR)

# Monte Carlo simulation (Block 4)
app.include_router(simulation.router, prefix=settings.API_V1_STR)

# Collaboration / Sharing (Block 5)
app.include_router(sharing.router, prefix=settings.API_V1_STR)

# External Curves (Block 6)
app.include_router(curves.router, prefix=settings.API_V1_STR)

# Phase 0: Entities (universal platform)
app.include_router(entities.router, prefix=settings.API_V1_STR)

# Revenue streams configuration
app.include_router(revenue_streams.router, prefix=settings.API_V1_STR)

# Phase 3: Consolidated view + intercompany eliminations
app.include_router(consolidated.router, prefix=settings.API_V1_STR)

# AI Settings (user API keys for AI ingestion)
app.include_router(ai_settings.router, prefix=settings.API_V1_STR)

# Admin — usage stats and user management (Fase 0.5.2)
app.include_router(admin.router, prefix=settings.API_V1_STR)


import redis
from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.base import get_db


@app.get("/health")
def health(db: Session = Depends(get_db)):
    db_status = "ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"
    
    redis_status = "ok"
    try:
        r = redis.Redis.from_url(settings.REDIS_URL)
        r.ping()
    except Exception:
        redis_status = "error"
        
    status = "ok" if db_status == "ok" and redis_status == "ok" else "error"
    
    return {
        "status": status,
        "service": settings.APP_NAME,
        "database": db_status,
        "redis": redis_status,
    }

@app.get("/metrics")
def metrics():
    # Simple custom JSON metrics for MVP.
    return {
        "status": "ok",
        "timestamp": time.time(),
        # For a full prometheus metrics endpoint, we would return plain text 
        # using prometheus_client library, but this suffices for the MVP JSON requirement.
    }
