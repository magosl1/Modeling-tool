"""Celery task definitions (stub for future async jobs)."""
import uuid
from datetime import datetime, timezone

from celery import Celery
from sqlalchemy import insert
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.base import SessionLocal
from app.models.entity import Entity
from app.models.project import Project, ProjectedFinancial, NOLBalance
from app.services.projections_runner import load_historical, load_assumptions, run_projection_engine

celery_app = Celery("financial_modeler", broker=settings.REDIS_URL)
celery_app.conf.update(
    result_backend=settings.REDIS_URL,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

@celery_app.task(bind=True, name="run_projections_async")
def run_projections_async(self, project_id: str):
    db: Session = SessionLocal()
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return {"status": "error", "detail": "Project not found"}
        
        pnl, bs, cf, hist_years = load_historical(project_id, db)
        if not hist_years:
            return {"status": "error", "detail": "No historical data uploaded."}

        assumptions = load_assumptions(project_id, db)
        result, proj_years = run_projection_engine(project, pnl, bs, cf, hist_years, assumptions)
        
        if result.errors:
            return {"status": "error", "detail": "Projection engine encountered errors", "errors": result.errors}

        entity = db.query(Entity).filter(Entity.project_id == project.id).order_by(Entity.display_order).first()
        if not entity:
            return {"status": "error", "detail": "Project has no entity."}

        db.query(ProjectedFinancial).filter(
            ProjectedFinancial.project_id == project_id,
            ProjectedFinancial.entity_id == entity.id,
            ProjectedFinancial.scenario_id == None,
        ).delete()
        db.query(NOLBalance).filter(NOLBalance.project_id == project_id).delete()

        def _rows_for_statement(data: dict, stmt_type: str) -> list:
            rows = []
            for line_item, year_vals in data.items():
                for year, value in year_vals.items():
                    rows.append({
                        "id": str(uuid.uuid4()),
                        "project_id": project_id,
                        "entity_id": entity.id,
                        "statement_type": stmt_type,
                        "line_item": line_item,
                        "year": year,
                        "value": value,
                    })
            return rows

        all_financial_rows = (
            _rows_for_statement(result.pnl, "PNL")
            + _rows_for_statement(result.bs, "BS")
            + _rows_for_statement(result.cf, "CF")
        )
        if all_financial_rows:
            db.execute(insert(ProjectedFinancial), all_financial_rows)

        nol_rows = [
            {
                "id": str(uuid.uuid4()),
                "project_id": project_id,
                "year": year,
                "nol_opening": nol["nol_opening"],
                "nol_used": nol["nol_used"],
                "nol_closing": nol["nol_closing"],
            }
            for year, nol in result.nol_balances.items()
        ]
        if nol_rows:
            db.execute(insert(NOLBalance), nol_rows)

        project.status = "projected"
        project.updated_at = datetime.now(timezone.utc)
        db.commit()

        return {
            "status": "success",
            "projection_years": proj_years,
            "warnings": result.warnings,
        }

    except Exception as e:
        db.rollback()
        return {"status": "error", "detail": str(e)}
    finally:
        db.close()
