from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi import File, UploadFile
from fastapi.responses import RedirectResponse, StreamingResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.forms import ManualAPRInput
from app.services.comparison_service import competencia_from_date, rerun_latest_comparisons_for_competencias
from app.services.manual_apr_service import (
    ManualAPRConflictError,
    create_manual_apr,
    delete_manual_apr,
    export_manual_aprs_csv_rows,
    get_manual_apr,
    import_manual_aprs_from_csv_bytes,
    import_manual_aprs_from_text,
    list_manual_aprs,
    update_manual_apr,
)
from app.utils.web import paginate, parse_optional_date, pop_flash, set_flash


router = APIRouter(prefix="/manual-aprs", tags=["manual-aprs"])


def _manual_sort_state(sort: str | None, direction: str | None) -> tuple[str, str]:
    allowed_sorts = {"apr_id", "data_referencia", "responsavel", "status", "updated_at"}
    safe_sort = sort if sort in allowed_sorts else "updated_at"
    safe_direction = "asc" if direction == "asc" else "desc"
    return safe_sort, safe_direction


@router.get("")
def manual_apr_list(
    request: Request,
    q: str | None = None,
    sort: str | None = None,
    direction: str | None = None,
    page: int = 1,
    db: Session = Depends(get_db),
) -> object:
    safe_sort, safe_direction = _manual_sort_state(sort, direction)
    pagination = paginate(
        list_manual_aprs(db, q, sort_by=safe_sort, direction=safe_direction),
        page,
        15,
    )
    context = {
        "request": request,
        "manual_aprs": pagination["items"],
        "query": q or "",
        "sort": safe_sort,
        "direction": safe_direction,
        "pagination": pagination,
        "form_data": {},
        "form_errors": [],
        "import_errors": [],
        "import_form_data": "",
        "flash": pop_flash(request),
    }
    return request.app.state.templates.TemplateResponse(request, "manual_aprs/index.html", context)


@router.post("")
def manual_apr_create(
    request: Request,
    apr_id: str = Form(...),
    data_referencia: str | None = Form(default=None),
    responsavel: str | None = Form(default=None),
    descricao: str | None = Form(default=None),
    observacao: str | None = Form(default=None),
    status_apr: str | None = Form(default=None, alias="status"),
    db: Session = Depends(get_db),
) -> object:
    form_data = {
        "apr_id": apr_id,
        "data_referencia": data_referencia or None,
        "responsavel": responsavel,
        "descricao": descricao,
        "observacao": observacao,
        "status": status_apr,
    }
    try:
        payload = ManualAPRInput(
            apr_id=apr_id,
            data_referencia=parse_optional_date(data_referencia),
            responsavel=responsavel,
            descricao=descricao,
            observacao=observacao,
            status=status_apr,
        )
        create_manual_apr(db, payload)
    except ManualAPRConflictError as exc:
        safe_sort, safe_direction = _manual_sort_state(None, None)
        pagination = paginate(list_manual_aprs(db, None, sort_by=safe_sort, direction=safe_direction), 1, 15)
        context = {
            "request": request,
            "manual_aprs": pagination["items"],
            "query": "",
            "sort": safe_sort,
            "direction": safe_direction,
            "pagination": pagination,
            "form_data": form_data,
            "form_errors": [str(exc)],
            "import_errors": [],
            "import_form_data": "",
            "flash": None,
        }
        return request.app.state.templates.TemplateResponse(
            request,
            "manual_aprs/index.html",
            context,
            status_code=status.HTTP_409_CONFLICT,
        )
    except (ValidationError, ValueError) as exc:
        errors = [error["msg"] for error in getattr(exc, "errors", lambda: [])()] or [str(exc)]
        safe_sort, safe_direction = _manual_sort_state(None, None)
        pagination = paginate(list_manual_aprs(db, None, sort_by=safe_sort, direction=safe_direction), 1, 15)
        context = {
            "request": request,
            "manual_aprs": pagination["items"],
            "query": "",
            "sort": safe_sort,
            "direction": safe_direction,
            "pagination": pagination,
            "form_data": form_data,
            "form_errors": errors,
            "import_errors": [],
            "import_form_data": "",
            "flash": None,
        }
        return request.app.state.templates.TemplateResponse(
            request,
            "manual_aprs/index.html",
            context,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    rerun_latest_comparisons_for_competencias(
        db,
        {competencia_from_date(payload.data_referencia)} - {None},
    )
    set_flash(request, "success", "APR manual cadastrada com sucesso.")
    return RedirectResponse(url="/manual-aprs", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/import")
def manual_apr_import(
    request: Request,
    import_text: str = Form(...),
    db: Session = Depends(get_db),
) -> object:
    try:
        result = import_manual_aprs_from_text(db, import_text)
    except (ManualAPRConflictError, ValidationError, ValueError) as exc:
        errors = [error["msg"] for error in getattr(exc, "errors", lambda: [])()] or [str(exc)]
        safe_sort, safe_direction = _manual_sort_state(None, None)
        pagination = paginate(list_manual_aprs(db, None, sort_by=safe_sort, direction=safe_direction), 1, 15)
        context = {
            "request": request,
            "manual_aprs": pagination["items"],
            "query": "",
            "sort": safe_sort,
            "direction": safe_direction,
            "pagination": pagination,
            "form_data": {},
            "form_errors": [],
            "import_errors": errors,
            "import_form_data": import_text,
            "flash": None,
        }
        return request.app.state.templates.TemplateResponse(
            request,
            "manual_aprs/index.html",
            context,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    rerun_latest_comparisons_for_competencias(db, result.competencias_afetadas)
    message = f"Importação manual concluída: {result.created_count} criada(s)"
    if result.skipped_count:
        message += f", {result.skipped_count} ignorada(s)"
    set_flash(request, "success", message + ".")
    return RedirectResponse(url="/manual-aprs", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/import-csv")
def manual_apr_import_csv(
    request: Request,
    arquivo: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> object:
    try:
        result = import_manual_aprs_from_csv_bytes(
            db,
            arquivo.filename or "base-manual.csv",
            arquivo.file.read(),
        )
    except (ManualAPRConflictError, ValidationError, ValueError) as exc:
        errors = [error["msg"] for error in getattr(exc, "errors", lambda: [])()] or [str(exc)]
        safe_sort, safe_direction = _manual_sort_state(None, None)
        pagination = paginate(list_manual_aprs(db, None, sort_by=safe_sort, direction=safe_direction), 1, 15)
        context = {
            "request": request,
            "manual_aprs": pagination["items"],
            "query": "",
            "sort": safe_sort,
            "direction": safe_direction,
            "pagination": pagination,
            "form_data": {},
            "form_errors": [],
            "import_errors": errors,
            "import_form_data": "",
            "flash": None,
        }
        return request.app.state.templates.TemplateResponse(
            request,
            "manual_aprs/index.html",
            context,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    rerun_latest_comparisons_for_competencias(db, result.competencias_afetadas)
    message = f"Importação CSV concluída: {result.created_count} criada(s)"
    if result.skipped_count:
        message += f", {result.skipped_count} ignorada(s)"
    set_flash(request, "success", message + ".")
    return RedirectResponse(url="/manual-aprs", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/{manual_apr_id}/delete")
def manual_apr_delete_confirm(
    request: Request,
    manual_apr_id: int,
    db: Session = Depends(get_db),
) -> object:
    manual_apr = get_manual_apr(db, manual_apr_id)
    if manual_apr is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="APR manual não encontrada.")
    context = {
        "request": request,
        "manual_apr": manual_apr,
        "flash": pop_flash(request),
    }
    return request.app.state.templates.TemplateResponse(
        request,
        "manual_aprs/delete.html",
        context,
    )


@router.post("/{manual_apr_id}/delete")
def manual_apr_delete(
    request: Request,
    manual_apr_id: int,
    confirm_apr_id: str = Form(...),
    db: Session = Depends(get_db),
) -> object:
    manual_apr = get_manual_apr(db, manual_apr_id)
    if manual_apr is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="APR manual não encontrada.")
    if confirm_apr_id.strip() != manual_apr.apr_id:
        context = {
            "request": request,
            "manual_apr": manual_apr,
            "form_errors": ["Confirmação inválida. Digite exatamente o APR ID informado."],
            "flash": None,
        }
        return request.app.state.templates.TemplateResponse(
            request,
            "manual_aprs/delete.html",
            context,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    affected_competencias = {competencia_from_date(manual_apr.data_referencia)} - {None}
    delete_manual_apr(db, manual_apr)
    rerun_latest_comparisons_for_competencias(db, affected_competencias)
    set_flash(request, "success", "APR manual excluída com sucesso.")
    return RedirectResponse(url="/manual-aprs", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/export")
def manual_apr_export_csv(
    q: str | None = None,
    sort: str | None = None,
    direction: str | None = None,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    safe_sort, safe_direction = _manual_sort_state(sort, direction)
    items = list_manual_aprs(db, q, sort_by=safe_sort, direction=safe_direction)
    stream = io.StringIO()
    writer = csv.writer(stream)
    for row in export_manual_aprs_csv_rows(items):
        writer.writerow(row)
    response = StreamingResponse(iter([stream.getvalue()]), media_type="text/csv; charset=utf-8")
    response.headers["Content-Disposition"] = 'attachment; filename="base_manual_aprs.csv"'
    return response
@router.get("/{manual_apr_id}/edit")
def manual_apr_edit_form(request: Request, manual_apr_id: int, db: Session = Depends(get_db)) -> object:
    manual_apr = get_manual_apr(db, manual_apr_id)
    if manual_apr is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="APR manual não encontrada.")
    context = {
        "request": request,
        "manual_apr": manual_apr,
        "form_errors": [],
        "flash": pop_flash(request),
    }
    return request.app.state.templates.TemplateResponse(request, "manual_aprs/edit.html", context)


@router.post("/{manual_apr_id}/edit")
def manual_apr_edit(
    request: Request,
    manual_apr_id: int,
    apr_id: str = Form(...),
    data_referencia: str | None = Form(default=None),
    responsavel: str | None = Form(default=None),
    descricao: str | None = Form(default=None),
    observacao: str | None = Form(default=None),
    status_apr: str | None = Form(default=None, alias="status"),
    db: Session = Depends(get_db),
) -> object:
    manual_apr = get_manual_apr(db, manual_apr_id)
    if manual_apr is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="APR manual não encontrada.")
    previous_competencia = competencia_from_date(manual_apr.data_referencia)
    try:
        payload = ManualAPRInput(
            apr_id=apr_id,
            data_referencia=parse_optional_date(data_referencia),
            responsavel=responsavel,
            descricao=descricao,
            observacao=observacao,
            status=status_apr,
        )
        update_manual_apr(db, manual_apr, payload)
    except ManualAPRConflictError as exc:
        context = {
            "request": request,
            "manual_apr": manual_apr,
            "form_errors": [str(exc)],
            "flash": None,
        }
        return request.app.state.templates.TemplateResponse(
            request,
            "manual_aprs/edit.html",
            context,
            status_code=status.HTTP_409_CONFLICT,
        )
    except (ValidationError, ValueError) as exc:
        errors = [error["msg"] for error in getattr(exc, "errors", lambda: [])()] or [str(exc)]
        context = {
            "request": request,
            "manual_apr": manual_apr,
            "form_errors": errors,
            "flash": None,
        }
        return request.app.state.templates.TemplateResponse(
            request,
            "manual_aprs/edit.html",
            context,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    rerun_latest_comparisons_for_competencias(
        db,
        {previous_competencia, competencia_from_date(payload.data_referencia)} - {None},
    )
    set_flash(request, "success", "APR manual atualizada com sucesso.")
    return RedirectResponse(url="/manual-aprs", status_code=status.HTTP_303_SEE_OTHER)
