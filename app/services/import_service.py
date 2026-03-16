from __future__ import annotations

import csv
import io
import json
import os
import xml.etree.ElementTree as ET
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

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
    if extension not in {".csv", ".tsv", ".txt", ".xml"}:
        raise ImportValidationError("Envie um arquivo CSV, TSV, TXT ou XML.")

    if extension in {".csv", ".tsv", ".txt"}:
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


def get_import_batch(db: Session, batch_id: int, *, include_deleted: bool = False) -> ImportBatch | None:
    batch = db.get(ImportBatch, batch_id)
    if batch is None:
        return None
    if batch.deleted_at is not None and not include_deleted:
        return None
    return batch


def delete_import_batch(db: Session, batch: ImportBatch) -> None:
    batch.deleted_at = datetime.now(UTC).replace(tzinfo=None)
    db.commit()


def parse_csv_bytes(raw_data: bytes) -> list[ParsedImportRow]:
    text = _prepare_csv_text(_decode_text(raw_data))
    stream = io.StringIO(text)
    reader = csv.DictReader(stream, dialect=_detect_csv_dialect(text))
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


def _detect_csv_dialect(text: str) -> csv.Dialect | type[csv.Dialect]:
    sample = text[:4096]
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;|\t")
    except csv.Error:
        return csv.excel


def _extract_xml_records(root: ET.Element) -> list[dict[str, str]]:
    repeated_candidates = _find_repeated_record_elements(root)
    if repeated_candidates:
        return [_element_to_payload(element) for element in repeated_candidates]

    apr_candidates = _find_elements_with_apr_id(root)
    if apr_candidates:
        return [_element_to_payload(element) for element in apr_candidates]

    payload = _element_to_payload(root)
    return [payload] if payload else []


def _element_to_payload(element: ET.Element) -> dict[str, str]:
    payload: dict[str, str] = {}
    for key, value in _extract_element_fields(element):
        payload[key] = value
    return payload


def _extract_element_fields(element: ET.Element, prefix: str = "") -> Iterable[tuple[str, str]]:
    for attr_name, attr_value in element.attrib.items():
        normalized_attr = _normalize_xml_tag(attr_name)
        if normalized_attr:
            yield prefix + normalized_attr, attr_value

    children = list(element)
    if not children:
        text = (element.text or "").strip()
        key = prefix + _normalize_xml_tag(element.tag)
        if key and text:
            yield key, text
        return

    for child in children:
        child_prefix = prefix
        if list(child):
            child_prefix = prefix + _normalize_xml_tag(child.tag) + "_"
        yield from _extract_element_fields(child, child_prefix)


def _normalize_xml_tag(tag: str) -> str:
    if "}" in tag:
        tag = tag.split("}", maxsplit=1)[1]
    return tag.strip()


def _prepare_csv_text(text: str) -> str:
    lines = text.splitlines()
    if not lines:
        return text

    start_index = 0
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        normalized = stripped.lower()
        if normalized.startswith("sep="):
            start_index = index + 1
            continue
        if _looks_like_csv_header(stripped):
            start_index = index
            break
    prepared = "\n".join(lines[start_index:]).strip()
    return prepared or text.strip()


def _looks_like_csv_header(line: str) -> bool:
    for delimiter in (",", ";", "\t", "|"):
        if delimiter not in line:
            continue
        columns = [part.strip().strip('"').strip("'") for part in line.split(delimiter)]
        if detect_apr_key(columns):
            return True
    return False


def _find_repeated_record_elements(root: ET.Element) -> list[ET.Element]:
    best: list[ET.Element] = []
    for parent in root.iter():
        children = list(parent)
        if len(children) < 2:
            continue
        grouped: dict[str, list[ET.Element]] = {}
        for child in children:
            grouped.setdefault(_normalize_xml_tag(child.tag), []).append(child)
        for elements in grouped.values():
            if len(elements) < 2:
                continue
            if any(detect_apr_key(_element_to_payload(element).keys()) for element in elements):
                if len(elements) > len(best):
                    best = elements
    return best


def _find_elements_with_apr_id(root: ET.Element) -> list[ET.Element]:
    candidates: list[ET.Element] = []
    for element in root.iter():
        payload = _element_to_payload(element)
        if payload and detect_apr_key(payload.keys()):
            candidates.append(element)
    if not candidates:
        return []

    filtered: list[ET.Element] = []
    for candidate in candidates:
        if any(candidate in list(parent) for parent in candidates if parent is not candidate):
            continue
        filtered.append(candidate)
    return filtered
