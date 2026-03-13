from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.dashboard_service import get_dashboard_summary
from app.utils.web import pop_flash


router = APIRouter()


@router.get("/")
def dashboard(request: Request, db: Session = Depends(get_db)) -> object:
    context = {
        "request": request,
        "summary": get_dashboard_summary(db),
        "flash": pop_flash(request),
    }
    return request.app.state.templates.TemplateResponse(request, "dashboard.html", context)
