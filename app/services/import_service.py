from __future__ import annotations

import csv
import io
import json
import os
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.models.entities import ImportBatch, ImportedAPR
from app.schemas.forms import ImportBatchInput
from app.services.apr_utils import detect_apr_key, normalize_apr_id


class ImportValidationError(ValueError):
    pass


@dataclass(slots=True)
class ParsedImportRow:
    apr_id: str | None
    payload: dict[str, object]
    is_valid: bool
    is_duplicate: bool = False
    error_message: str | None = None


def create_import_batch(db: Session, upload: UploadFile, payload: ImportBatchInput) -> ImportBatch:
    filename = upload.filename or "arquivo_sem_nome"
    extension = os.path.splitext(filename)[1].lower()
    raw_data = upload.file.read()
    if extension not in {".csv", ".xml"}:
        raise ImportValidationError("Envie um arquivo CSV ou XML.")

    if extension == ".csv":
        parsed_rows = parse_csv_bytes(raw_data)
    else:
        parsed_rows = parse_xml_bytes(raw_data)

    batch = ImportBatch(
        nome_arquivo=filename,
        tipo_arquivo=extension.lstrip("."),
        competencia=payload.competencia,
        total_registros=len(parsed_rows),
        total_validos=sum(1 for row in parsed_rows if row.is_valid),
        total_invalidos=sum(1 for row in parsed_rows if not row.is_valid and not row.is_duplicate),
        total_duplicados=sum(1 for row in parsed_rows if row.is_duplicate),
    )
    db.add(batch)
    db.flush()

    for row in parsed_rows:
        imported = ImportedAPR(
            batch_id=batch.id,
            apr_id=row.apr_id,
            payload_json=json.dumps(row.payload, ensure_ascii=False, default=str),
            is_valid=row.is_valid,
            is_duplicate=row.is_duplicate,
            error_message=row.error_message,
        )
        db.add(imported)

    db.commit()
    db.refresh(batch)
    return batch


def parse_csv_bytes(raw_data: bytes) -> list[ParsedImportRow]:
    text = _decode_text(raw_data)
    stream = io.StringIO(text)
    reader = csv.DictReader(stream)
    if not reader.fieldnames:
        raise ImportValidationError("O CSV não possui cabeçalho.")

    id_key = detect_apr_key(reader.fieldnames)
    if not id_key:
        raise ImportValidationError("Não foi possível identificar a coluna do ID da APR no CSV.")

    rows: list[ParsedImportRow] = []
    for index, row in enumerate(reader, start=2):
        payload = {key: (value or "").strip() for key, value in row.items() if key}
        apr_id = normalize_apr_id(payload.get(id_key))
        if not apr_id:
            rows.append(
                ParsedImportRow(
                    apr_id=None,
                    payload=payload,
                    is_valid=False,
                    error_message=f"Linha {index}: apr_id ausente ou vazio.",
                )
            )
            continue
        payload[id_key] = apr_id
        rows.append(ParsedImportRow(apr_id=apr_id, payload=payload, is_valid=True))

    return _mark_duplicate_rows(rows)


def parse_xml_bytes(raw_data: bytes) -> list[ParsedImportRow]:
    text = _decode_text(raw_data)
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise ImportValidationError("O XML informado é inválido.") from exc

    records = _extract_xml_records(root)
    if not records:
        raise ImportValidationError("Não foi possível identificar registros de APR no XML.")

    rows: list[ParsedImportRow] = []
    for index, payload in enumerate(records, start=1):
        id_key = detect_apr_key(payload.keys())
        apr_id = normalize_apr_id(payload.get(id_key)) if id_key else None
        normalized_payload = {
            key: value.strip() if isinstance(value, str) else value for key, value in payload.items()
        }
        if not apr_id:
            rows.append(
                ParsedImportRow(
                    apr_id=None,
                    payload=normalized_payload,
                    is_valid=False,
                    error_message=f"Registro XML {index}: apr_id ausente ou vazio.",
                )
            )
            continue
        normalized_payload[id_key or "apr_id"] = apr_id
        rows.append(ParsedImportRow(apr_id=apr_id, payload=normalized_payload, is_valid=True))

    return _mark_duplicate_rows(rows)


def _mark_duplicate_rows(rows: list[ParsedImportRow]) -> list[ParsedImportRow]:
    counts = Counter(row.apr_id for row in rows if row.is_valid and row.apr_id)
    for row in rows:
        if row.is_valid and row.apr_id and counts[row.apr_id] > 1:
            row.is_valid = False
            row.is_duplicate = True
            row.error_message = "apr_id duplicado dentro do mesmo lote."
    return rows


def _decode_text(raw_data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return raw_data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ImportValidationError("Não foi possível decodificar o arquivo enviado.")


def _extract_xml_records(root: ET.Element) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    for parent in root.iter():
        children = list(parent)
        if not children:
            continue
        child_payload = {
            _normalize_xml_tag(child.tag): (child.text or "")
            for child in children
            if len(list(child)) == 0
        }
        if child_payload and detect_apr_key(child_payload.keys()):
            candidates.append(child_payload)
    return candidates


def _normalize_xml_tag(tag: str) -> str:
    if "}" in tag:
        tag = tag.split("}", maxsplit=1)[1]
    return tag.strip()
