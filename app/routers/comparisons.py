from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.comparison_service import get_comparison_run, run_comparison
from app.utils.web import pop_flash, set_flash


router = APIRouter(prefix="/comparisons", tags=["comparisons"])


@router.post("/run/{batch_id}")
def execute_comparison(request: Request, batch_id: int, db: Session = Depends(get_db)) -> object:
    comparison_run = run_comparison(db, batch_id)
    if comparison_run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lote não encontrado.")
    set_flash(request, "success", "Conciliação executada com sucesso.")
    return RedirectResponse(
        url=f"/comparisons/{comparison_run.id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/{run_id}")
def comparison_detail(
    request: Request,
    run_id: int,
    status_filter: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
) -> object:
    comparison_run = get_comparison_run(db, run_id)
    if comparison_run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comparação não encontrada.")
    items = comparison_run.items
    if status_filter:
        items = [item for item in items if item.status_comparacao == status_filter]
    context = {
        "request": request,
        "comparison_run": comparison_run,
        "items": items,
        "status_filter": status_filter or "",
        "flash": pop_flash(request),
    }
    return request.app.state.templates.TemplateResponse("comparisons/detail.html", context)
