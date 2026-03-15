from __future__ import annotations

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
from app.utils.web import pop_flash, set_flash


router = APIRouter(prefix="/imports", tags=["imports"])


@router.get("")
def imports_page(
    request: Request,
    batch_id: int | None = None,
    db: Session = Depends(get_db),
) -> object:
    selected_batch = None
    selected_batch_latest_batch_run = None
    selected_batch_latest_competencia_run = None
    selected_batch_preview_by_row_id: dict[int, dict[str, str]] = {}
    if batch_id is not None:
        selected_batch = db.scalar(
            select(ImportBatch)
            .options(selectinload(ImportBatch.imported_aprs), selectinload(ImportBatch.comparison_runs))
            .where(ImportBatch.id == batch_id)
        )
        if selected_batch is not None:
            batch_runs = [run for run in selected_batch.comparison_runs if run.scope_type == "batch"]
            if batch_runs:
                selected_batch_latest_batch_run = batch_runs[0]
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
    batches = list(db.scalars(select(ImportBatch).order_by(ImportBatch.created_at.desc(), ImportBatch.id.desc())))
    context = {
        "request": request,
        "batches": batches,
        "selected_batch": selected_batch,
        "selected_batch_latest_batch_run": selected_batch_latest_batch_run,
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
        batches = list(db.scalars(select(ImportBatch).order_by(ImportBatch.created_at.desc(), ImportBatch.id.desc())))
        context = {
            "request": request,
            "batches": batches,
            "selected_batch": None,
            "selected_batch_latest_batch_run": None,
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
    return RedirectResponse(url=f"/imports?batch_id={batch.id}", status_code=status.HTTP_303_SEE_OTHER)


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
