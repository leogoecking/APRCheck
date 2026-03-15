from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.forms import ManualAPRInput
from app.services.comparison_service import rerun_all_comparisons
from app.services.manual_apr_service import (
    ManualAPRConflictError,
    create_manual_apr,
    get_manual_apr,
    list_manual_aprs,
    update_manual_apr,
)
from app.utils.web import parse_optional_date, pop_flash, set_flash


router = APIRouter(prefix="/manual-aprs", tags=["manual-aprs"])


@router.get("")
def manual_apr_list(request: Request, q: str | None = None, db: Session = Depends(get_db)) -> object:
    context = {
        "request": request,
        "manual_aprs": list_manual_aprs(db, q),
        "query": q or "",
        "form_data": {},
        "form_errors": [],
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
        context = {
            "request": request,
            "manual_aprs": list_manual_aprs(db),
            "query": "",
            "form_data": form_data,
            "form_errors": [str(exc)],
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
        context = {
            "request": request,
            "manual_aprs": list_manual_aprs(db),
            "query": "",
            "form_data": form_data,
            "form_errors": errors,
            "flash": None,
        }
        return request.app.state.templates.TemplateResponse(
            request,
            "manual_aprs/index.html",
            context,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    rerun_all_comparisons(db)
    set_flash(request, "success", "APR manual cadastrada com sucesso.")
    return RedirectResponse(url="/manual-aprs", status_code=status.HTTP_303_SEE_OTHER)


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

    rerun_all_comparisons(db)
    set_flash(request, "success", "APR manual atualizada com sucesso.")
    return RedirectResponse(url="/manual-aprs", status_code=status.HTTP_303_SEE_OTHER)
