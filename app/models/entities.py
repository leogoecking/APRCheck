from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text, desc, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), nullable=False
    )


class ManualAPR(TimestampMixin, Base):
    __tablename__ = "manual_aprs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    apr_id: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    data_referencia: Mapped[date | None] = mapped_column(Date, nullable=True)
    responsavel: Mapped[str | None] = mapped_column(String(255), nullable=True)
    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)
    observacao: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str | None] = mapped_column(String(80), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class ImportBatch(TimestampMixin, Base):
    __tablename__ = "import_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome_arquivo: Mapped[str] = mapped_column(String(255), nullable=False)
    tipo_arquivo: Mapped[str] = mapped_column(String(20), nullable=False)
    competencia: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    total_registros: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_validos: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_invalidos: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_duplicados: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    imported_aprs: Mapped[list["ImportedAPR"]] = relationship(
        back_populates="batch",
        cascade="all, delete-orphan",
        order_by=lambda: ImportedAPR.id,
    )
    comparison_runs: Mapped[list["ComparisonRun"]] = relationship(
        back_populates="batch",
        cascade="all, delete-orphan",
        order_by=lambda: desc(ComparisonRun.id),
    )


class ImportedAPR(TimestampMixin, Base):
    __tablename__ = "imported_aprs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("import_batches.id"), nullable=False, index=True)
    apr_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    is_valid: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    batch: Mapped["ImportBatch"] = relationship(back_populates="imported_aprs")


class ComparisonRun(TimestampMixin, Base):
    __tablename__ = "comparison_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("import_batches.id"), nullable=False, index=True)
    competencia: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    total_manual: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_importado: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_conciliado: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_faltando_manual: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_faltando_importado: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_duplicados: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_invalidos: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    batch: Mapped["ImportBatch"] = relationship(back_populates="comparison_runs")
    items: Mapped[list["ComparisonItem"]] = relationship(
        back_populates="comparison_run",
        cascade="all, delete-orphan",
        order_by=lambda: ComparisonItem.id,
    )


class ComparisonItem(TimestampMixin, Base):
    __tablename__ = "comparison_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    comparison_run_id: Mapped[int] = mapped_column(
        ForeignKey("comparison_runs.id"),
        nullable=False,
        index=True,
    )
    apr_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    origem: Mapped[str] = mapped_column(String(30), nullable=False)
    status_comparacao: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    detalhe: Mapped[str | None] = mapped_column(Text, nullable=True)

    comparison_run: Mapped["ComparisonRun"] = relationship(back_populates="items")


Index("ix_imported_aprs_batch_id_apr_id", ImportedAPR.batch_id, ImportedAPR.apr_id)
Index("ix_comparison_items_run_status", ComparisonItem.comparison_run_id, ComparisonItem.status_comparacao)
