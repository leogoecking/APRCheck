from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import ComparisonRun, ImportBatch, ImportedAPR, ManualAPR


def get_dashboard_summary(db: Session) -> dict[str, object]:
    total_manual = db.scalar(select(func.count()).select_from(ManualAPR)) or 0
    total_imported = db.scalar(select(func.count()).select_from(ImportedAPR)) or 0
    total_batches = db.scalar(select(func.count()).select_from(ImportBatch)) or 0
    total_duplicates = db.scalar(
        select(func.count()).select_from(ImportedAPR).where(ImportedAPR.is_duplicate.is_(True))
    ) or 0
    latest_run = db.scalar(select(ComparisonRun).order_by(ComparisonRun.created_at.desc(), ComparisonRun.id.desc()))

    return {
        "total_manual": total_manual,
        "total_imported": total_imported,
        "total_batches": total_batches,
        "total_duplicates": total_duplicates,
        "latest_run": latest_run,
        "total_conciliated": latest_run.total_conciliado if latest_run else 0,
        "missing_manual": latest_run.total_faltando_manual if latest_run else 0,
        "missing_imported": latest_run.total_faltando_importado if latest_run else 0,
    }
