from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.forms import DivergenceFilters
from app.services.comparison_service import list_divergence_items
from app.utils.web import paginate, pop_flash


router = APIRouter(prefix="/divergences", tags=["divergences"])


def _divergence_sort_state(sort: str | None, direction: str | None) -> tuple[str, str]:
    allowed_sorts = {"competencia", "batch_id", "comparison_id", "apr_id", "categoria", "created_at"}
    safe_sort = sort if sort in allowed_sorts else "created_at"
    safe_direction = "asc" if direction == "asc" else "desc"
    return safe_sort, safe_direction


@router.get("")
def divergences_page(
    request: Request,
    competencia: str | None = None,
    categoria: str | None = None,
    apr_id: str | None = None,
    sort: str | None = None,
    direction: str | None = None,
    page: int = 1,
    db: Session = Depends(get_db),
) -> object:
    filters = DivergenceFilters(competencia=competencia, categoria=categoria, apr_id=apr_id)
    safe_sort, safe_direction = _divergence_sort_state(sort, direction)
    all_items = list_divergence_items(
        db,
        competencia=filters.competencia,
        categoria=filters.categoria,
        apr_id=filters.apr_id,
        sort_by=safe_sort,
        direction=safe_direction,
    )
    pagination = paginate(all_items, page, 20)
    context = {
        "request": request,
        "items": pagination["items"],
        "filters": filters,
        "sort": safe_sort,
        "direction": safe_direction,
        "pagination": pagination,
        "flash": pop_flash(request),
    }
    return request.app.state.templates.TemplateResponse(request, "divergences/index.html", context)


@router.get("/export")
def export_divergences(
    competencia: str | None = None,
    categoria: str | None = None,
    apr_id: str | None = None,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    filters = DivergenceFilters(competencia=competencia, categoria=categoria, apr_id=apr_id)
    items = list_divergence_items(
        db,
        competencia=filters.competencia,
        categoria=filters.categoria,
        apr_id=filters.apr_id,
    )
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(
        [
            "competencia",
            "lote_id",
            "comparison_run_id",
            "apr_id",
            "assunto",
            "data_abertura",
            "categoria",
            "origem",
            "detalhe",
        ]
    )
    for item, comparison_run, batch, preview in items:
        writer.writerow(
            [
                comparison_run.competencia,
                batch.id,
                comparison_run.id,
                item.apr_id or "",
                preview.get("assunto", ""),
                preview.get("data_abertura", ""),
                item.status_comparacao,
                item.origem,
                item.detalhe or "",
            ]
        )
    response = StreamingResponse(iter([stream.getvalue()]), media_type="text/csv; charset=utf-8")
    response.headers["Content-Disposition"] = 'attachment; filename="divergencias.csv"'
    return response
