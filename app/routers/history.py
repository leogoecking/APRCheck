from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.models.entities import ComparisonRun, ImportBatch, ManualAPRAuditLog
from app.services.comparison_service import ensure_latest_competencia_runs
from app.utils.web import paginate, pop_flash


router = APIRouter(prefix="/history", tags=["history"])


def _history_sort_state(sort: str | None, direction: str | None, allowed: set[str], default: str) -> tuple[str, str]:
    safe_sort = sort if sort in allowed else default
    safe_direction = "asc" if direction == "asc" else "desc"
    return safe_sort, safe_direction


@router.get("")
def history_page(
    request: Request,
    import_page: int = 1,
    comparison_page: int = 1,
    audit_page: int = 1,
    import_sort: str | None = None,
    import_direction: str | None = None,
    comparison_sort: str | None = None,
    comparison_direction: str | None = None,
    db: Session = Depends(get_db),
) -> object:
    ensure_latest_competencia_runs(db, competencia=None)
    import_sort, import_direction = _history_sort_state(
        import_sort,
        import_direction,
        {"id", "competencia", "total_registros", "created_at"},
        "created_at",
    )
    comparison_sort, comparison_direction = _history_sort_state(
        comparison_sort,
        comparison_direction,
        {"id", "competencia", "created_at"},
        "created_at",
    )
    import_order_map = {
        "id": ImportBatch.id,
        "competencia": ImportBatch.competencia,
        "total_registros": ImportBatch.total_registros,
        "created_at": ImportBatch.created_at,
    }
    comparison_order_map = {
        "id": ComparisonRun.id,
        "competencia": ComparisonRun.competencia,
        "created_at": ComparisonRun.created_at,
    }
    batches = list(
        db.scalars(
            select(ImportBatch)
            .options(selectinload(ImportBatch.comparison_runs))
            .where(ImportBatch.deleted_at.is_(None))
            .order_by(
                import_order_map[import_sort].asc() if import_direction == "asc" else import_order_map[import_sort].desc(),
                ImportBatch.id.desc(),
            )
        )
    )
    comparisons = list(
        db.scalars(
            select(ComparisonRun)
            .options(selectinload(ComparisonRun.batch))
            .where(ComparisonRun.scope_type == "competencia")
            .order_by(
                comparison_order_map[comparison_sort].asc()
                if comparison_direction == "asc"
                else comparison_order_map[comparison_sort].desc(),
                ComparisonRun.id.desc(),
            )
        )
    )
    audits = list(
        db.scalars(
            select(ManualAPRAuditLog).order_by(ManualAPRAuditLog.created_at.desc(), ManualAPRAuditLog.id.desc())
        )
    )
    import_pagination = paginate(batches, import_page, 10)
    comparison_pagination = paginate(comparisons, comparison_page, 10)
    audit_pagination = paginate(audits, audit_page, 10)
    context = {
        "request": request,
        "batches": import_pagination["items"],
        "comparisons": comparison_pagination["items"],
        "audits": audit_pagination["items"],
        "import_pagination": import_pagination,
        "comparison_pagination": comparison_pagination,
        "audit_pagination": audit_pagination,
        "import_sort": import_sort,
        "import_direction": import_direction,
        "comparison_sort": comparison_sort,
        "comparison_direction": comparison_direction,
        "flash": pop_flash(request),
    }
    return request.app.state.templates.TemplateResponse(request, "history/index.html", context)
