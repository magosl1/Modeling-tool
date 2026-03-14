import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import auth, projects, historical, assumptions, projections, valuation, templates, ratios, metadata
from app.core.config import settings

logger = logging.getLogger("uvicorn.access")

app = FastAPI(
    title=settings.APP_NAME,
    description="Financial Modeling Platform — MVP",
    version="1.0.0",
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "%s %s %d %.1fms",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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


@app.get("/health")
def health():
    return {"status": "ok", "service": settings.APP_NAME}
