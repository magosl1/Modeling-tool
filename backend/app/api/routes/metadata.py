"""Single source of truth for line-item definitions used by frontend and backend."""
from fastapi import APIRouter

from app.services.template_generator import BS_ITEMS, CF_ITEMS, PNL_ITEMS

router = APIRouter(prefix="/metadata", tags=["metadata"])


@router.get("/line-items")
def get_line_items():
    """Return canonical line-item lists for P&L, BS and CF statements."""
    return {
        "PNL": [{"name": name, "sign": sign} for name, sign in PNL_ITEMS],
        "BS": [{"name": name, "bucket": bucket, "sign": sign} for name, bucket, sign in BS_ITEMS],
        "CF": [{"name": name, "sign": sign} for name, sign in CF_ITEMS],
    }
