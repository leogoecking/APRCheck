from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.entities import ManualAPR
from app.schemas.forms import ManualAPRInput


class ManualAPRConflictError(ValueError):
    pass


def list_manual_aprs(db: Session, query: str | None = None) -> list[ManualAPR]:
    statement = select(ManualAPR).order_by(ManualAPR.updated_at.desc(), ManualAPR.id.desc())
    if query:
        statement = statement.where(ManualAPR.apr_id.contains(query.strip()))
    return list(db.scalars(statement))


def get_manual_apr(db: Session, apr_db_id: int) -> ManualAPR | None:
    return db.get(ManualAPR, apr_db_id)


def create_manual_apr(db: Session, payload: ManualAPRInput) -> ManualAPR:
    manual_apr = ManualAPR(**payload.model_dump())
    db.add(manual_apr)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ManualAPRConflictError("O apr_id informado já existe no cadastro manual.") from exc
    db.refresh(manual_apr)
    return manual_apr


def update_manual_apr(db: Session, manual_apr: ManualAPR, payload: ManualAPRInput) -> ManualAPR:
    for field, value in payload.model_dump().items():
        setattr(manual_apr, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ManualAPRConflictError("O apr_id informado já existe no cadastro manual.") from exc
    db.refresh(manual_apr)
    return manual_apr
