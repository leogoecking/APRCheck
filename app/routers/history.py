from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.models.entities import ComparisonRun, ImportBatch
from app.utils.web import pop_flash


router = APIRouter(prefix="/history", tags=["history"])


@router.get("")
def history_page(request: Request, db: Session = Depends(get_db)) -> object:
    batches = list(
        db.scalars(
            select(ImportBatch)
            .options(selectinload(ImportBatch.comparison_runs))
            .order_by(ImportBatch.created_at.desc(), ImportBatch.id.desc())
        )
    )
    comparisons = list(
        db.scalars(
            select(ComparisonRun)
            .options(selectinload(ComparisonRun.batch))
            .order_by(ComparisonRun.created_at.desc(), ComparisonRun.id.desc())
        )
    )
    context = {
        "request": request,
        "batches": batches,
        "comparisons": comparisons,
        "flash": pop_flash(request),
    }
    return request.app.state.templates.TemplateResponse(request, "history/index.html", context)
