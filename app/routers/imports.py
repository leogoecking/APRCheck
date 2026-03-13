from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status
from fastapi.responses import RedirectResponse
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.models.entities import ImportBatch
from app.schemas.forms import ImportBatchInput
from app.services.import_service import ImportValidationError, create_import_batch
from app.utils.web import pop_flash, set_flash


router = APIRouter(prefix="/imports", tags=["imports"])


@router.get("")
def imports_page(
    request: Request,
    batch_id: int | None = None,
    db: Session = Depends(get_db),
) -> object:
    selected_batch = None
    if batch_id is not None:
        selected_batch = db.scalar(
            select(ImportBatch)
            .options(selectinload(ImportBatch.imported_aprs), selectinload(ImportBatch.comparison_runs))
            .where(ImportBatch.id == batch_id)
        )
    batches = list(db.scalars(select(ImportBatch).order_by(ImportBatch.created_at.desc(), ImportBatch.id.desc())))
    context = {
        "request": request,
        "batches": batches,
        "selected_batch": selected_batch,
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
