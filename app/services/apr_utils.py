from __future__ import annotations

import re
from collections.abc import Iterable


APR_KEY_CANDIDATES = (
    "apr_id",
    "aprid",
    "id_apr",
    "idapr",
    "codigoapr",
    "codigo_apr",
    "numeroapr",
    "numero_apr",
    "id",
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
    return None
