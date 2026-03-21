from __future__ import annotations

from dataclasses import dataclass

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import RedirectResponse
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.models.entities import ComparisonRun, ImportBatch
from app.schemas.forms import ImportBatchInput
from app.services.comparison_service import rerun_latest_comparisons_for_competencias, extract_visual_fields
from app.services.import_service import (
    ImportValidationError,
    create_import_batch,
    delete_import_batch,
    get_import_batch,
)
from app.services.apr_utils import normalize_competencia
from app.utils.web import pop_flash, set_flash


router = APIRouter(prefix="/imports", tags=["imports"])


@dataclass(slots=True)
class MonthlyImportSummary:
    competencia: str
    batch_count: int
    total_registros: int
    total_validos: int
    total_invalidos: int
    total_duplicados: int
    latest_batch_id: int


def _build_monthly_import_summaries(batches: list[ImportBatch]) -> list[MonthlyImportSummary]:
    grouped: dict[str, list[ImportBatch]] = {}
    for batch in batches:
        grouped.setdefault(batch.competencia, []).append(batch)

    summaries: list[MonthlyImportSummary] = []
    for competencia, competencia_batches in grouped.items():
        latest_batch = max(competencia_batches, key=lambda item: (item.created_at, item.id))
        summaries.append(
            MonthlyImportSummary(
                competencia=competencia,
                batch_count=len(competencia_batches),
                total_registros=sum(item.total_registros for item in competencia_batches),
                total_validos=sum(item.total_validos for item in competencia_batches),
                total_invalidos=sum(item.total_invalidos for item in competencia_batches),
                total_duplicados=sum(item.total_duplicados for item in competencia_batches),
                latest_batch_id=latest_batch.id,
            )
        )
    summaries.sort(key=lambda item: item.competencia, reverse=True)
    return summaries


@router.get("")
def imports_page(
    request: Request,
    batch_id: int | None = None,
    competencia: str | None = None,
    db: Session = Depends(get_db),
) -> object:
    batches = list(
        db.scalars(
            select(ImportBatch)
            .where(ImportBatch.deleted_at.is_(None))
            .order_by(ImportBatch.created_at.desc(), ImportBatch.id.desc())
        )
    )
    monthly_summaries = _build_monthly_import_summaries(batches)
    selected_batch = None
    selected_batch_latest_competencia_run = None
    selected_batch_preview_by_row_id: dict[int, dict[str, str]] = {}
    if batch_id is not None:
        selected_batch = db.scalar(
            select(ImportBatch)
            .options(selectinload(ImportBatch.imported_aprs), selectinload(ImportBatch.comparison_runs))
            .where(ImportBatch.id == batch_id, ImportBatch.deleted_at.is_(None))
        )
        if selected_batch is not None:
            selected_batch_latest_competencia_run = db.scalar(
                select(ComparisonRun)
                .where(
                    ComparisonRun.scope_type == "competencia",
                    ComparisonRun.scope_value == selected_batch.competencia,
                )
                .order_by(ComparisonRun.created_at.desc(), ComparisonRun.id.desc())
            )
            selected_batch_preview_by_row_id = {
                row.id: extract_visual_fields(row.payload_json) for row in selected_batch.imported_aprs
            }
    selected_competencia = normalize_competencia(competencia) if competencia else None
    if selected_competencia is None and selected_batch is not None:
        selected_competencia = selected_batch.competencia
    if selected_competencia is None and monthly_summaries:
        selected_competencia = monthly_summaries[0].competencia
    selected_competencia_summary = next(
        (item for item in monthly_summaries if item.competencia == selected_competencia),
        None,
    )
    selected_competencia_batches = [
        batch for batch in batches if batch.competencia == selected_competencia
    ]
    selected_competencia_latest_run = None
    if selected_competencia is not None:
        selected_competencia_latest_run = db.scalar(
            select(ComparisonRun)
            .where(
                ComparisonRun.scope_type == "competencia",
                ComparisonRun.scope_value == selected_competencia,
            )
            .order_by(ComparisonRun.created_at.desc(), ComparisonRun.id.desc())
        )
    context = {
        "request": request,
        "batches": batches,
        "monthly_summaries": monthly_summaries,
        "selected_competencia": selected_competencia,
        "selected_competencia_summary": selected_competencia_summary,
        "selected_competencia_batches": selected_competencia_batches,
        "selected_competencia_latest_run": selected_competencia_latest_run,
        "selected_batch": selected_batch,
        "selected_batch_latest_competencia_run": selected_batch_latest_competencia_run,
        "selected_batch_preview_by_row_id": selected_batch_preview_by_row_id,
        "form_errors": [],
        "flash": pop_flash(request),
    }
    return request.app.state.templates.TemplateResponse(request, "imports/index.html", context)


@router.post("")
def import_file(
    request: Request,
    competencia: str = Form(...),
    arquivo: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> object:
    try:
        payload = ImportBatchInput(competencia=competencia)
        batch = create_import_batch(db, arquivo, payload)
    except (ValidationError, ImportValidationError, ValueError) as exc:
        errors = [error["msg"] for error in getattr(exc, "errors", lambda: [])()] or [str(exc)]
        batches = list(
            db.scalars(
                select(ImportBatch)
                .where(ImportBatch.deleted_at.is_(None))
                .order_by(ImportBatch.created_at.desc(), ImportBatch.id.desc())
            )
        )
        context = {
            "request": request,
            "batches": batches,
            "monthly_summaries": _build_monthly_import_summaries(batches),
            "selected_competencia": None,
            "selected_competencia_summary": None,
            "selected_competencia_batches": [],
            "selected_competencia_latest_run": None,
            "selected_batch": None,
            "selected_batch_latest_competencia_run": None,
            "selected_batch_preview_by_row_id": {},
            "form_errors": errors,
            "flash": None,
        }
        return request.app.state.templates.TemplateResponse(
            request,
            "imports/index.html",
            context,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    set_flash(request, "success", "Arquivo importado com sucesso.")
    return RedirectResponse(
        url=f"/imports?competencia={batch.competencia}&batch_id={batch.id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/{batch_id}/delete")
def import_batch_delete_confirm(
    request: Request,
    batch_id: int,
    db: Session = Depends(get_db),
) -> object:
    batch = get_import_batch(db, batch_id)
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lote não encontrado.")
    context = {
        "request": request,
        "batch": batch,
        "form_errors": [],
        "flash": pop_flash(request),
    }
    return request.app.state.templates.TemplateResponse(request, "imports/delete.html", context)


@router.post("/{batch_id}/delete")
def import_batch_delete(
    request: Request,
    batch_id: int,
    confirm_batch_id: str = Form(...),
    db: Session = Depends(get_db),
) -> object:
    batch = get_import_batch(db, batch_id)
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lote não encontrado.")
    if confirm_batch_id.strip() != str(batch.id):
        context = {
            "request": request,
            "batch": batch,
            "form_errors": ["Confirmação inválida. Digite exatamente o ID do lote."],
            "flash": None,
        }
        return request.app.state.templates.TemplateResponse(
            request,
            "imports/delete.html",
            context,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    competencia = batch.competencia
    delete_import_batch(db, batch)
    rerun_latest_comparisons_for_competencias(db, {competencia})
    set_flash(request, "success", "Lote importado excluído com sucesso.")
    return RedirectResponse(url="/imports", status_code=status.HTTP_303_SEE_OTHER)
