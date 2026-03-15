from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.entities import ComparisonItem, ComparisonRun, ImportBatch, ImportedAPR, ManualAPR


def run_comparison(db: Session, batch_id: int) -> ComparisonRun | None:
    batch = db.scalar(
        select(ImportBatch)
        .options(
            selectinload(ImportBatch.imported_aprs),
            selectinload(ImportBatch.comparison_runs).selectinload(ComparisonRun.items),
        )
        .where(ImportBatch.id == batch_id)
    )
    if batch is None:
        return None

    for existing_run in list(batch.comparison_runs):
        db.delete(existing_run)
    db.flush()

    manual_ids = set(db.scalars(select(ManualAPR.apr_id)))
    imported_valid_ids = {
        row.apr_id
        for row in batch.imported_aprs
        if row.is_valid and not row.is_duplicate and row.apr_id
    }
    duplicate_ids = sorted({row.apr_id for row in batch.imported_aprs if row.is_duplicate and row.apr_id})
    invalid_rows = [row for row in batch.imported_aprs if not row.is_valid and not row.is_duplicate]

    conciliated_ids = sorted(manual_ids & imported_valid_ids)
    missing_manual_ids = sorted(imported_valid_ids - manual_ids)
    missing_imported_ids = sorted(manual_ids - imported_valid_ids)

    comparison_run = ComparisonRun(
        batch_id=batch.id,
        competencia=batch.competencia,
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
            detalhe="ID presente no cadastro manual e no lote importado.",
        )
        for apr_id in conciliated_ids
    )
    items.extend(
        ComparisonItem(
            comparison_run_id=comparison_run.id,
            apr_id=apr_id,
            origem="importado",
            status_comparacao="faltando_no_manual",
            detalhe="ID encontrado no lote importado e ausente no cadastro manual.",
        )
        for apr_id in missing_manual_ids
    )
    items.extend(
        ComparisonItem(
            comparison_run_id=comparison_run.id,
            apr_id=apr_id,
            origem="manual",
            status_comparacao="faltando_no_importado",
            detalhe="ID encontrado no cadastro manual e ausente no lote importado.",
        )
        for apr_id in missing_imported_ids
    )
    items.extend(
        ComparisonItem(
            comparison_run_id=comparison_run.id,
            apr_id=apr_id,
            origem="importado",
            status_comparacao="duplicado",
            detalhe="ID duplicado detectado dentro do lote importado.",
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


def get_comparison_run(db: Session, run_id: int) -> ComparisonRun | None:
    return db.scalar(
        select(ComparisonRun)
        .options(
            selectinload(ComparisonRun.items),
            selectinload(ComparisonRun.batch).selectinload(ImportBatch.imported_aprs),
        )
        .where(ComparisonRun.id == run_id)
    )


def rerun_all_comparisons(db: Session) -> list[ComparisonRun]:
    batch_ids = list(
        db.scalars(select(ImportBatch.id).order_by(ImportBatch.created_at.asc(), ImportBatch.id.asc()))
    )
    results: list[ComparisonRun] = []
    for batch_id in batch_ids:
        comparison_run = run_comparison(db, batch_id)
        if comparison_run is not None:
            results.append(comparison_run)
    return results


def list_divergence_items(
    db: Session,
    *,
    competencia: str | None = None,
    categoria: str | None = None,
    apr_id: str | None = None,
) -> list[tuple[ComparisonItem, ComparisonRun, ImportBatch]]:
    statement = (
        select(ComparisonItem, ComparisonRun, ImportBatch)
        .join(ComparisonRun, ComparisonItem.comparison_run_id == ComparisonRun.id)
        .join(ImportBatch, ComparisonRun.batch_id == ImportBatch.id)
        .where(ComparisonItem.status_comparacao != "conciliado")
        .order_by(ComparisonItem.created_at.desc(), ComparisonItem.id.desc())
    )
    if competencia:
        statement = statement.where(ComparisonRun.competencia == competencia)
    if categoria:
        statement = statement.where(ComparisonItem.status_comparacao == categoria)
    if apr_id:
        statement = statement.where(ComparisonItem.apr_id == apr_id)
    return list(db.execute(statement).all())
