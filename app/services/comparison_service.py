from __future__ import annotations

from collections import Counter
from datetime import date
import json

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.entities import ComparisonItem, ComparisonRun, ImportBatch, ImportedAPR, ManualAPR
from app.services.apr_utils import (
    competencia_variants,
    detect_open_date_key,
    detect_subject_key,
    normalize_competencia,
    normalize_open_date,
)


def run_batch_comparison(db: Session, batch_id: int) -> ComparisonRun | None:
    batch = db.scalar(
        select(ImportBatch)
        .options(selectinload(ImportBatch.imported_aprs))
        .where(ImportBatch.id == batch_id, ImportBatch.deleted_at.is_(None))
    )
    if batch is None:
        return None

    return _create_comparison_run(
        db,
        competencia=batch.competencia,
        scope_type="batch",
        scope_value=str(batch.id),
        imported_rows=batch.imported_aprs,
        source_batches=[batch],
        reference_batch=batch,
    )


def run_competencia_comparison(db: Session, competencia: str) -> ComparisonRun | None:
    cleaned_competencia = normalize_competencia(competencia)
    if not cleaned_competencia:
        return None

    variants = competencia_variants(cleaned_competencia)

    batches = list(
        db.scalars(
            select(ImportBatch)
            .options(selectinload(ImportBatch.imported_aprs))
            .where(ImportBatch.deleted_at.is_(None), ImportBatch.competencia.in_(variants))
            .order_by(ImportBatch.created_at.asc(), ImportBatch.id.asc())
        )
    )
    if not batches:
        return None

    imported_rows = [row for batch in batches for row in batch.imported_aprs]
    return _create_comparison_run(
        db,
        competencia=cleaned_competencia,
        scope_type="competencia",
        scope_value=cleaned_competencia,
        imported_rows=imported_rows,
        source_batches=batches,
        reference_batch=batches[-1],
    )


def _create_comparison_run(
    db: Session,
    *,
    competencia: str,
    scope_type: str,
    scope_value: str,
    imported_rows: list[ImportedAPR],
    source_batches: list[ImportBatch],
    reference_batch: ImportBatch,
) -> ComparisonRun:
    manual_ids = _load_manual_ids_for_competencia(db, competencia)
    imported_valid_ids, duplicate_ids, invalid_rows = _build_import_snapshot(imported_rows)

    conciliated_ids = sorted(manual_ids & imported_valid_ids)
    missing_manual_ids = sorted(imported_valid_ids - manual_ids)
    missing_imported_ids = sorted(manual_ids - imported_valid_ids)

    comparison_run = ComparisonRun(
        batch_id=reference_batch.id,
        competencia=competencia,
        scope_type=scope_type,
        scope_value=scope_value,
        source_batch_ids=",".join(str(batch.id) for batch in source_batches),
        total_manual=len(manual_ids),
        total_importado=len(imported_valid_ids),
        total_conciliado=len(conciliated_ids),
        total_faltando_manual=len(missing_manual_ids),
        total_faltando_importado=len(missing_imported_ids),
        total_duplicados=len(duplicate_ids),
        total_invalidos=len(invalid_rows),
    )
    db.add(comparison_run)
    db.flush()

    items: list[ComparisonItem] = []
    items.extend(
        ComparisonItem(
            comparison_run_id=comparison_run.id,
            apr_id=apr_id,
            origem="ambos",
            status_comparacao="conciliado",
            detalhe="ID presente no cadastro manual e no escopo importado selecionado.",
        )
        for apr_id in conciliated_ids
    )
    items.extend(
        ComparisonItem(
            comparison_run_id=comparison_run.id,
            apr_id=apr_id,
            origem="importado",
            status_comparacao="faltando_no_manual",
            detalhe="ID encontrado no escopo importado e ausente no cadastro manual da competência.",
        )
        for apr_id in missing_manual_ids
    )
    items.extend(
        ComparisonItem(
            comparison_run_id=comparison_run.id,
            apr_id=apr_id,
            origem="manual",
            status_comparacao="faltando_no_importado",
            detalhe="ID encontrado no cadastro manual da competência e ausente no escopo importado.",
        )
        for apr_id in missing_imported_ids
    )
    items.extend(
        ComparisonItem(
            comparison_run_id=comparison_run.id,
            apr_id=apr_id,
            origem="importado",
            status_comparacao="duplicado",
            detalhe="ID duplicado detectado dentro do escopo importado selecionado.",
        )
        for apr_id in duplicate_ids
    )
    items.extend(
        ComparisonItem(
            comparison_run_id=comparison_run.id,
            apr_id=row.apr_id,
            origem="importado",
            status_comparacao="invalido",
            detalhe=row.error_message or "Registro inválido no lote importado.",
        )
        for row in invalid_rows
    )
    db.add_all(items)
    db.commit()
    db.refresh(comparison_run)
    return comparison_run


def _load_manual_ids_for_competencia(db: Session, competencia: str) -> set[str]:
    normalized_competencia = normalize_competencia(competencia)
    if normalized_competencia is None:
        return set()
    return set(
        db.scalars(
            select(ManualAPR.apr_id).where(
                func.strftime("%Y-%m", ManualAPR.data_referencia) == normalized_competencia
            )
        )
    )


def _build_import_snapshot(imported_rows: list[ImportedAPR]) -> tuple[set[str], list[str], list[ImportedAPR]]:
    valid_rows = [row for row in imported_rows if row.is_valid and not row.is_duplicate and row.apr_id]
    counts = Counter(row.apr_id for row in valid_rows if row.apr_id)
    duplicate_ids = sorted(
        {
            *(row.apr_id for row in imported_rows if row.is_duplicate and row.apr_id),
            *(apr_id for apr_id, count in counts.items() if count > 1),
        }
    )
    imported_valid_ids = {
        row.apr_id
        for row in valid_rows
        if row.apr_id and counts[row.apr_id] == 1
    }
    invalid_rows = [row for row in imported_rows if not row.is_valid and not row.is_duplicate]
    return imported_valid_ids, duplicate_ids, invalid_rows


def get_comparison_run(db: Session, run_id: int) -> ComparisonRun | None:
    return db.scalar(
        select(ComparisonRun)
        .options(
            selectinload(ComparisonRun.items),
            selectinload(ComparisonRun.batch).selectinload(ImportBatch.imported_aprs),
        )
        .where(ComparisonRun.id == run_id)
    )


def build_import_preview_map(imported_rows: list[ImportedAPR]) -> dict[str, dict[str, str]]:
    preview_map: dict[str, dict[str, str]] = {}
    for row in imported_rows:
        if not row.apr_id or row.apr_id in preview_map:
            continue
        preview_map[row.apr_id] = extract_visual_fields(row.payload_json)
    return preview_map


def extract_visual_fields(payload_json: str) -> dict[str, str]:
    try:
        payload = json.loads(payload_json)
    except json.JSONDecodeError:
        return {"assunto": "", "data_abertura": ""}
    if not isinstance(payload, dict):
        return {"assunto": "", "data_abertura": ""}

    subject_key = detect_subject_key(payload.keys())
    open_date_key = detect_open_date_key(payload.keys())
    assunto = str(payload.get(subject_key, "")).strip() if subject_key else ""
    data_abertura = normalize_open_date(payload.get(open_date_key)) or ""
    return {"assunto": assunto, "data_abertura": data_abertura}


def rerun_latest_comparisons_for_competencias(
    db: Session,
    competencias: set[str],
) -> list[ComparisonRun]:
    results: list[ComparisonRun] = []
    for competencia in sorted(filter(None, competencias)):
        normalized_competencia = normalize_competencia(competencia)
        if normalized_competencia is None:
            continue
        latest_competencia_run = db.scalar(
            select(ComparisonRun)
            .where(
                ComparisonRun.scope_type == "competencia",
                ComparisonRun.scope_value == normalized_competencia,
            )
            .order_by(ComparisonRun.created_at.desc(), ComparisonRun.id.desc())
        )
        if latest_competencia_run is not None:
            comparison_run = run_competencia_comparison(db, normalized_competencia)
            if comparison_run is not None:
                results.append(comparison_run)
    return results


def ensure_latest_competencia_runs(
    db: Session,
    *,
    competencia: str | None = None,
) -> list[ComparisonRun]:
    competencias = (
        [competencia]
        if competencia
        else list(
            db.scalars(
                select(ImportBatch.competencia)
                .distinct()
                .where(ImportBatch.deleted_at.is_(None))
                .order_by(ImportBatch.competencia.asc())
            )
        )
    )
    results: list[ComparisonRun] = []
    for item in competencias:
        normalized_item = normalize_competencia(item)
        if not normalized_item:
            continue
        latest_competencia_run = db.scalar(
            select(ComparisonRun)
            .where(
                ComparisonRun.scope_type == "competencia",
                ComparisonRun.scope_value == normalized_item,
            )
            .order_by(ComparisonRun.created_at.desc(), ComparisonRun.id.desc())
        )

        needs_refresh = latest_competencia_run is None
        if latest_competencia_run is not None:
            latest_import = db.scalar(
                select(ImportBatch.created_at)
                .where(
                    ImportBatch.deleted_at.is_(None),
                    ImportBatch.competencia.in_(competencia_variants(normalized_item)),
                )
                .order_by(ImportBatch.created_at.desc(), ImportBatch.id.desc())
            )
            if latest_import is not None:
                needs_refresh = latest_import > latest_competencia_run.created_at

        if needs_refresh:
            comparison_run = run_competencia_comparison(db, normalized_item)
            if comparison_run is not None:
                results.append(comparison_run)
    return results


def competencia_from_date(value: date | None) -> str | None:
    if value is None:
        return None
    return value.strftime("%Y-%m")


def parse_source_batch_ids(value: str | None) -> list[int]:
    if not value:
        return []
    return [int(item) for item in value.split(",") if item.strip().isdigit()]


def list_divergence_items(
    db: Session,
    *,
    competencia: str | None = None,
    categoria: str | None = None,
    apr_id: str | None = None,
    sort_by: str = "created_at",
    direction: str = "desc",
) -> list[tuple[ComparisonItem, ComparisonRun, ImportBatch, dict[str, str]]]:
    latest_runs_subquery = (
        select(func.max(ComparisonRun.id).label("id"))
        .where(ComparisonRun.scope_type == "competencia")
        .group_by(ComparisonRun.scope_value)
        .subquery()
    )
    sort_map = {
        "competencia": ComparisonRun.competencia,
        "batch_id": ImportBatch.id,
        "comparison_id": ComparisonRun.id,
        "apr_id": ComparisonItem.apr_id,
        "categoria": ComparisonItem.status_comparacao,
        "created_at": ComparisonItem.created_at,
    }
    order_column = sort_map.get(sort_by, ComparisonItem.created_at)
    order_clause = order_column.asc() if direction == "asc" else order_column.desc()
    statement = (
        select(ComparisonItem, ComparisonRun, ImportBatch)
        .join(ComparisonRun, ComparisonItem.comparison_run_id == ComparisonRun.id)
        .join(ImportBatch, ComparisonRun.batch_id == ImportBatch.id)
        .join(latest_runs_subquery, latest_runs_subquery.c.id == ComparisonRun.id)
        .where(ComparisonItem.status_comparacao != "conciliado")
        .order_by(order_clause, ComparisonItem.id.desc())
    )
    if competencia:
        statement = statement.where(ComparisonRun.competencia == competencia)
    if categoria:
        statement = statement.where(ComparisonItem.status_comparacao == categoria)
    if apr_id:
        statement = statement.where(ComparisonItem.apr_id == apr_id)
    rows = list(db.execute(statement).all())
    preview_map: dict[int, dict[str, dict[str, str]]] = {}
    result: list[tuple[ComparisonItem, ComparisonRun, ImportBatch, dict[str, str]]] = []
    for item, comparison_run, batch in rows:
        if comparison_run.id not in preview_map:
            source_batch_ids = parse_source_batch_ids(comparison_run.source_batch_ids) or [batch.id]
            imported_rows = list(
                db.scalars(
                    select(ImportedAPR)
                    .where(ImportedAPR.batch_id.in_(source_batch_ids))
                    .order_by(ImportedAPR.id.asc())
                )
            )
            preview_map[comparison_run.id] = build_import_preview_map(imported_rows)
        result.append(
            (
                item,
                comparison_run,
                batch,
                preview_map[comparison_run.id].get(item.apr_id or "", {"assunto": "", "data_abertura": ""}),
            )
        )
    return result
