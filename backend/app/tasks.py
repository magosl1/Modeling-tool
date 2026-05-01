"""Celery task definitions (stub for future async jobs)."""
import uuid
from datetime import datetime, timezone

from celery import Celery
from sqlalchemy import insert
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.base import SessionLocal
from app.models.entity import Entity
from app.models.project import NOLBalance, Project, ProjectedFinancial
from app.services.projections_runner import load_assumptions, load_historical, run_projection_engine

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

        entities = (
            db.query(Entity)
            .filter(Entity.project_id == project.id)
            .order_by(Entity.display_order)
            .all()
        )
        if not entities:
            return {"status": "error", "detail": "Project has no entity."}

        # NOL is project-level — reset once before the per-entity loop.
        db.query(NOLBalance).filter(NOLBalance.project_id == project_id).delete()

        aggregated_warnings: list = []
        aggregated_proj_years: list = []
        runs_persisted = 0
        skipped: list = []
        nol_persisted = False

        for entity in entities:
            pnl, bs, cf, hist_years = load_historical(project_id, db, entity_id=entity.id)
            if not hist_years:
                skipped.append(f"{entity.name} (no historical)")
                continue

            assumptions = load_assumptions(project_id, db, entity_id=entity.id)
            if not assumptions:
                skipped.append(f"{entity.name} (no assumptions)")
                continue

            result, proj_years = run_projection_engine(project, pnl, bs, cf, hist_years, assumptions)

            if result.errors:
                return {
                    "status": "error",
                    "detail": f"Projection engine errors for entity '{entity.name}'",
                    "errors": result.errors,
                }

            db.query(ProjectedFinancial).filter(
                ProjectedFinancial.project_id == project_id,
                ProjectedFinancial.entity_id == entity.id,
                ProjectedFinancial.scenario_id == None,
            ).delete()

            rows: list = []
            for stmt_type, data in (("PNL", result.pnl), ("BS", result.bs), ("CF", result.cf)):
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
            if rows:
                db.execute(insert(ProjectedFinancial), rows)

            if not nol_persisted and result.nol_balances:
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
                db.execute(insert(NOLBalance), nol_rows)
                nol_persisted = True

            runs_persisted += 1
            aggregated_warnings.extend(f"[{entity.name}] {w}" for w in result.warnings)
            aggregated_proj_years = proj_years

        if runs_persisted == 0:
            return {
                "status": "error",
                "detail": (
                    "No entity has both historical data and assumptions yet. "
                    + ("Skipped: " + "; ".join(skipped) if skipped else "")
                ),
            }

        project.status = "projected"
        project.updated_at = datetime.now(timezone.utc)
        db.commit()

        return {
            "status": "success",
            "projection_years": aggregated_proj_years,
            "warnings": aggregated_warnings,
            "skipped_entities": skipped,
            "runs_persisted": runs_persisted,
        }

    except Exception as e:
        db.rollback()
        return {"status": "error", "detail": str(e)}
    finally:
        db.close()
