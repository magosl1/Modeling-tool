from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import auth, projects, historical, assumptions, projections, valuation, templates, ratios
from app.core.config import settings

app = FastAPI(
    title=settings.APP_NAME,
    description="Financial Modeling Platform — MVP",
    version="1.0.0",
)

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


@app.get("/health")
def health():
    return {"status": "ok", "service": settings.APP_NAME}
