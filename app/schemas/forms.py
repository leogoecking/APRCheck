from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, field_validator

from app.services.apr_utils import normalize_apr_id


class ManualAPRInput(BaseModel):
    apr_id: str = Field(min_length=1, max_length=120)
    data_referencia: date | None = None
    responsavel: str | None = Field(default=None, max_length=255)
    descricao: str | None = None
    observacao: str | None = None
    status: str | None = Field(default=None, max_length=80)

    @field_validator("apr_id")
    @classmethod
    def normalize_id(cls, value: str) -> str:
        normalized = normalize_apr_id(value)
        if not normalized:
            raise ValueError("Informe um apr_id válido.")
        return normalized


class ImportBatchInput(BaseModel):
    competencia: str = Field(min_length=1, max_length=20)

    @field_validator("competencia")
    @classmethod
    def validate_competencia(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Informe a competência do lote.")
        return cleaned


class DivergenceFilters(BaseModel):
    competencia: str | None = None
    categoria: str | None = None
    apr_id: str | None = None

    @field_validator("apr_id")
    @classmethod
    def normalize_optional_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = normalize_apr_id(value)
        return normalized or None
