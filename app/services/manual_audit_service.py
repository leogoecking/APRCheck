from __future__ import annotations

from app.models.entities import ManualAPR, ManualAPRAuditLog


def build_manual_apr_summary(manual_apr: ManualAPR) -> str:
    parts = [
        f"apr_id={manual_apr.apr_id}",
        f"data_abertura={manual_apr.data_referencia.isoformat() if manual_apr.data_referencia else ''}",
        f"colaborador={manual_apr.responsavel or ''}",
        f"assunto={manual_apr.descricao or ''}",
    ]
    return " | ".join(parts)


def build_bulk_import_summary(*, created_count: int, skipped_count: int) -> str:
    return f"criadas={created_count} | ignoradas={skipped_count}"


def create_manual_audit_log(
    *,
    action: str,
    apr_id: str,
    manual_apr_id: int | None,
    competencia: str | None,
    detalhe: str | None,
) -> ManualAPRAuditLog:
    return ManualAPRAuditLog(
        action=action,
        apr_id=apr_id,
        manual_apr_id=manual_apr_id,
        competencia=competencia,
        detalhe=detalhe,
    )
