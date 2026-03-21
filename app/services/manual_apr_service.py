from __future__ import annotations

import csv
import io
import os
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models.entities import ManualAPR, ManualAPRImportBatch
from app.schemas.forms import ManualAPRInput
from app.services.apr_utils import (
    detect_subject_key,
    normalize_apr_id,
    normalize_header,
    normalize_open_date,
)
from app.services.manual_audit_service import (
    build_bulk_delete_summary,
    build_bulk_import_summary,
    build_manual_apr_summary,
    create_manual_audit_log,
)


class ManualAPRConflictError(ValueError):
    pass


@dataclass(slots=True)
class ManualImportResult:
    created_count: int
    skipped_count: int
    errors: list[str]
    competencias_afetadas: set[str]


def classify_manual_reference_month(
    data_referencia: date | None,
    *,
    today: date | None = None,
) -> str:
    if data_referencia is None:
        return "sem_data"

    reference_today = today or date.today()
    current_month = reference_today.replace(day=1)
    previous_month = (current_month - timedelta(days=1)).replace(day=1)
    apr_month = data_referencia.replace(day=1)

    if apr_month == current_month:
        return "mes_atual"
    if apr_month == previous_month:
        return "mes_anterior"
    return "outro_mes"


def list_manual_aprs(
    db: Session,
    query: str | None = None,
    *,
    sort_by: str = "updated_at",
    direction: str = "desc",
) -> list[ManualAPR]:
    statement = select(ManualAPR)
    if query:
        statement = statement.where(ManualAPR.apr_id.contains(query.strip()))
    statement = statement.order_by(*_build_manual_order(sort_by, direction))
    return list(db.scalars(statement))


def get_manual_apr(db: Session, apr_db_id: int) -> ManualAPR | None:
    return db.get(ManualAPR, apr_db_id)


def list_manual_import_batches(db: Session) -> list[ManualAPRImportBatch]:
    return list(
        db.scalars(
            select(ManualAPRImportBatch)
            .options(selectinload(ManualAPRImportBatch.manual_aprs))
            .order_by(ManualAPRImportBatch.created_at.desc(), ManualAPRImportBatch.id.desc())
        )
    )


def get_manual_import_batch(db: Session, batch_id: int) -> ManualAPRImportBatch | None:
    return db.scalar(
        select(ManualAPRImportBatch)
        .options(selectinload(ManualAPRImportBatch.manual_aprs))
        .where(ManualAPRImportBatch.id == batch_id)
    )


def create_manual_apr(db: Session, payload: ManualAPRInput) -> ManualAPR:
    manual_apr = ManualAPR(**payload.model_dump())
    db.add(manual_apr)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ManualAPRConflictError("O apr_id informado já existe no cadastro manual.") from exc
    db.add(
        create_manual_audit_log(
            action="create",
            apr_id=manual_apr.apr_id,
            manual_apr_id=manual_apr.id,
            competencia=manual_apr.data_referencia.strftime("%Y-%m") if manual_apr.data_referencia else None,
            detalhe=build_manual_apr_summary(manual_apr),
        )
    )
    db.commit()
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
    db.add(
        create_manual_audit_log(
            action="update",
            apr_id=manual_apr.apr_id,
            manual_apr_id=manual_apr.id,
            competencia=manual_apr.data_referencia.strftime("%Y-%m") if manual_apr.data_referencia else None,
            detalhe=build_manual_apr_summary(manual_apr),
        )
    )
    db.commit()
    db.refresh(manual_apr)
    return manual_apr


def delete_manual_apr(db: Session, manual_apr: ManualAPR) -> None:
    audit_log = create_manual_audit_log(
        action="delete",
        apr_id=manual_apr.apr_id,
        manual_apr_id=manual_apr.id,
        competencia=manual_apr.data_referencia.strftime("%Y-%m") if manual_apr.data_referencia else None,
        detalhe=build_manual_apr_summary(manual_apr),
    )
    db.add(audit_log)
    db.delete(manual_apr)
    db.commit()


def import_manual_aprs_from_text(db: Session, raw_text: str) -> ManualImportResult:
    rows = _parse_manual_import_rows(raw_text)
    if not rows:
        raise ValueError("Informe ao menos uma linha para a importação manual.")

    existing_ids = set(db.scalars(select(ManualAPR.apr_id)))
    seen_ids: set[str] = set()
    to_create: list[ManualAPR] = []
    errors: list[str] = []
    competencias_afetadas: set[str] = set()

    for index, payload in rows:
        apr_id = payload.apr_id
        if apr_id in seen_ids:
            errors.append(f"Linha {index}: apr_id duplicado dentro da importação manual.")
            continue
        if apr_id in existing_ids:
            errors.append(f"Linha {index}: apr_id já cadastrado manualmente.")
            continue
        seen_ids.add(apr_id)
        existing_ids.add(apr_id)
        to_create.append(ManualAPR(**payload.model_dump()))
        if payload.data_referencia is not None:
            competencias_afetadas.add(payload.data_referencia.strftime("%Y-%m"))

    if to_create:
        batch = ManualAPRImportBatch(
            nome_arquivo="importacao_manual.txt",
            tipo_arquivo="txt",
            total_criadas=len(to_create),
            total_ignoradas=len(errors),
        )
        db.add(batch)
        db.flush()
        for item in to_create:
            item.manual_import_batch_id = batch.id
        db.add_all(to_create)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise ManualAPRConflictError("Falha ao importar APRs manuais por duplicidade de apr_id.") from exc
        db.add(
            create_manual_audit_log(
                action="bulk_import",
                apr_id=f"{len(to_create)}_itens",
                manual_apr_id=None,
                competencia=",".join(sorted(competencias_afetadas)) or None,
                detalhe=build_bulk_import_summary(
                    created_count=len(to_create),
                    skipped_count=len(errors),
                ),
            )
        )
        db.commit()

    return ManualImportResult(
        created_count=len(to_create),
        skipped_count=len(errors),
        errors=errors,
        competencias_afetadas=competencias_afetadas,
    )


def import_manual_aprs_from_csv_bytes(db: Session, filename: str, raw_data: bytes) -> ManualImportResult:
    extension = os.path.splitext(filename)[1].lower()
    if extension not in {".csv", ".tsv", ".txt"}:
        raise ValueError("Envie um arquivo CSV, TSV ou TXT para a base manual.")
    text = _decode_manual_text(raw_data)
    result = import_manual_aprs_from_text(db, text)
    if result.created_count:
        latest_batch = db.scalar(
            select(ManualAPRImportBatch).order_by(ManualAPRImportBatch.id.desc())
        )
        if latest_batch is not None:
            latest_batch.nome_arquivo = filename
            latest_batch.tipo_arquivo = extension.lstrip(".")
            db.commit()
    return result


def delete_manual_import_batch(
    db: Session,
    batch: ManualAPRImportBatch,
) -> set[str]:
    competencias_afetadas = {
        item.data_referencia.strftime("%Y-%m")
        for item in batch.manual_aprs
        if item.data_referencia is not None
    }
    deleted_count = len(batch.manual_aprs)
    db.add(
        create_manual_audit_log(
            action="bulk_delete",
            apr_id=f"{deleted_count}_itens",
            manual_apr_id=None,
            competencia=",".join(sorted(competencias_afetadas)) or None,
            detalhe=build_bulk_delete_summary(
                deleted_count=deleted_count,
                filename=batch.nome_arquivo,
            ),
        )
    )
    for item in list(batch.manual_aprs):
        db.delete(item)
    db.delete(batch)
    db.commit()
    return competencias_afetadas


def export_manual_aprs_csv_rows(items: list[ManualAPR]) -> list[list[str]]:
    rows = [
        [
            "apr_id",
            "data_abertura",
            "assunto",
            "colaborador",
            "created_at",
            "updated_at",
        ]
    ]
    for item in items:
        rows.append(
            [
                item.apr_id,
                item.data_referencia.isoformat() if item.data_referencia else "",
                item.descricao or "",
                item.responsavel or "",
                item.created_at.isoformat(sep=" ", timespec="seconds"),
                item.updated_at.isoformat(sep=" ", timespec="seconds"),
            ]
        )
    return rows


def _parse_manual_import_rows(raw_text: str) -> list[tuple[int, ManualAPRInput]]:
    text = raw_text.strip()
    if not text:
        return []
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) > 1 and _looks_like_structured_data(lines[0]):
        return _parse_structured_manual_rows(text)
    return _parse_simple_manual_rows(lines)


def _decode_manual_text(raw_data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return raw_data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("Não foi possível decodificar o arquivo CSV manual.")


def _parse_simple_manual_rows(lines: list[str]) -> list[tuple[int, ManualAPRInput]]:
    rows: list[tuple[int, ManualAPRInput]] = []
    for index, line in enumerate(lines, start=1):
        apr_id = normalize_apr_id(line)
        if not apr_id:
            raise ValueError(f"Linha {index}: apr_id ausente ou vazio.")
        rows.append((index, ManualAPRInput(apr_id=apr_id)))
    return rows


def _parse_structured_manual_rows(text: str) -> list[tuple[int, ManualAPRInput]]:
    reader = csv.DictReader(io.StringIO(text), dialect=_detect_manual_csv_dialect(text))
    if not reader.fieldnames:
        raise ValueError("Não foi possível identificar cabeçalhos na importação manual.")

    apr_key = _detect_manual_key(reader.fieldnames, ("apr_id", "aprid", "id_apr", "idapr", "id"))
    if not apr_key:
        raise ValueError("Não foi possível identificar a coluna do apr_id na importação manual.")
    date_key = _detect_manual_key(reader.fieldnames, ("data_referencia", "dataabertura", "abertura", "data"))
    subject_key = detect_subject_key(reader.fieldnames)
    status_key = _detect_manual_key(reader.fieldnames, ("status", "situacao"))
    responsavel_key = _detect_manual_key(reader.fieldnames, ("responsavel", "colaborador", "tecnico"))
    observacao_key = _detect_manual_key(reader.fieldnames, ("observacao", "observacoes", "nota"))

    rows: list[tuple[int, ManualAPRInput]] = []
    for index, row in enumerate(reader, start=2):
        apr_id = normalize_apr_id(row.get(apr_key))
        if not apr_id:
            raise ValueError(f"Linha {index}: apr_id ausente ou vazio.")
        rows.append(
            (
                index,
                ManualAPRInput(
                    apr_id=apr_id,
                    data_referencia=_parse_manual_date(row.get(date_key)) if date_key else None,
                    responsavel=_clean_optional(row.get(responsavel_key)) if responsavel_key else None,
                    descricao=_clean_optional(row.get(subject_key)) if subject_key else None,
                    observacao=_clean_optional(row.get(observacao_key)) if observacao_key else None,
                    status=_clean_optional(row.get(status_key)) if status_key else None,
                ),
            )
        )
    return rows


def _detect_manual_csv_dialect(text: str) -> csv.Dialect | type[csv.Dialect]:
    sample = text[:4096]
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;|\t")
    except csv.Error:
        return csv.excel


def _looks_like_structured_data(first_line: str) -> bool:
    normalized_headers = {normalize_header(part) for part in re_split(first_line)}
    return bool(
        normalized_headers
        & {
            "aprid",
            "idapr",
            "id",
            "descricao",
            "assunto",
            "dataabertura",
            "datareferencia",
        }
    )


def re_split(line: str) -> list[str]:
    for delimiter in (";", ",", "\t", "|"):
        if delimiter in line:
            return [part.strip() for part in line.split(delimiter)]
    return [line.strip()]


def _detect_manual_key(keys: list[str], candidates: tuple[str, ...]) -> str | None:
    normalized_map = {normalize_header(key): key for key in keys if key}
    for candidate in candidates:
        if candidate in normalized_map:
            return normalized_map[candidate]
    for normalized_key, original_key in normalized_map.items():
        for candidate in candidates:
            if normalized_key.endswith(candidate):
                return original_key
    return None


def _parse_manual_date(value: object) -> date | None:
    normalized = normalize_open_date(value)
    if not normalized:
        return None
    if len(normalized) == 10 and normalized[4] == "-":
        return date.fromisoformat(normalized)
    if len(normalized) == 10 and normalized[2] == "/":
        day, month, year = normalized.split("/")
        return date(int(year), int(month), int(day))
    raise ValueError(f"Data inválida na importação manual: {normalized}")


def _clean_optional(value: object) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _build_manual_order(sort_by: str, direction: str) -> tuple[object, ...]:
    sort_map = {
        "apr_id": ManualAPR.apr_id,
        "data_referencia": ManualAPR.data_referencia,
        "descricao": ManualAPR.descricao,
        "responsavel": ManualAPR.responsavel,
        "updated_at": ManualAPR.updated_at,
    }
    column = sort_map.get(sort_by, ManualAPR.updated_at)
    if direction == "asc":
        return (column.asc(), ManualAPR.id.asc())
    return (column.desc(), ManualAPR.id.desc())
