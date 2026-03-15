from __future__ import annotations

import re
from collections.abc import Iterable


APR_KEY_CANDIDATES = (
    "apr_id",
    "aprid",
    "id_apr",
    "idapr",
    "apr",
    "codigoapr",
    "codigo_apr",
    "codapr",
    "cod_apr",
    "codigodaapr",
    "codigo_da_apr",
    "numeroapr",
    "numero_apr",
    "nroapr",
    "nro_apr",
    "numerodaapr",
    "numero_da_apr",
    "identificadorapr",
)

FALLBACK_APR_KEY_CANDIDATES = (
    "id",
)

SUBJECT_KEY_CANDIDATES = (
    "assunto",
    "titulo",
    "descricao",
    "descricao",
    "resumo",
    "motivo",
)

OPEN_DATE_KEY_CANDIDATES = (
    "dataabertura",
    "dtabertura",
    "abertura",
    "data",
    "dataregistro",
    "datareferencia",
)


def normalize_apr_id(value: object) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def normalize_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.strip().lower())


def detect_apr_key(keys: Iterable[str]) -> str | None:
    normalized_map = {normalize_header(key): key for key in keys if key is not None}
    for candidate in APR_KEY_CANDIDATES:
        if candidate in normalized_map:
            return normalized_map[candidate]
    for normalized_key, original_key in normalized_map.items():
        for candidate in APR_KEY_CANDIDATES:
            if normalized_key.endswith(candidate):
                return original_key
    for candidate in FALLBACK_APR_KEY_CANDIDATES:
        if candidate in normalized_map:
            return normalized_map[candidate]
    return None


def detect_subject_key(keys: Iterable[str]) -> str | None:
    return _detect_key(keys, SUBJECT_KEY_CANDIDATES)


def detect_open_date_key(keys: Iterable[str]) -> str | None:
    return _detect_key(keys, OPEN_DATE_KEY_CANDIDATES)


def normalize_open_date(value: object) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    if not cleaned:
        return None
    if "T" in cleaned:
        cleaned = cleaned.split("T", maxsplit=1)[0]
    if " " in cleaned:
        cleaned = cleaned.split(" ", maxsplit=1)[0]
    if len(cleaned) >= 10 and cleaned[4] == "-" and cleaned[7] == "-":
        return cleaned[:10]
    if len(cleaned) >= 10 and cleaned[2] == "/" and cleaned[5] == "/":
        return cleaned[:10]
    return cleaned


def _detect_key(keys: Iterable[str], candidates: tuple[str, ...]) -> str | None:
    normalized_map = {normalize_header(key): key for key in keys if key is not None}
    for candidate in candidates:
        if candidate in normalized_map:
            return normalized_map[candidate]
    for normalized_key, original_key in normalized_map.items():
        for candidate in candidates:
            if normalized_key.endswith(candidate):
                return original_key
    return None
