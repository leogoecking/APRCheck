from __future__ import annotations

from datetime import date
from math import ceil

from starlette.requests import Request


def set_flash(request: Request, level: str, message: str) -> None:
    if "session" not in request.scope:
        return
    request.session["_flash"] = {"level": level, "message": message}


def pop_flash(request: Request) -> dict[str, str] | None:
    if "session" not in request.scope:
        return None
    return request.session.pop("_flash", None)


def parse_optional_date(value: str | None) -> date | None:
    if not value:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    return date.fromisoformat(cleaned)


def paginate(items: list[object], page: int, per_page: int) -> dict[str, object]:
    safe_per_page = max(1, per_page)
    total_items = len(items)
    total_pages = max(1, ceil(total_items / safe_per_page)) if total_items else 1
    safe_page = min(max(1, page), total_pages)
    start = (safe_page - 1) * safe_per_page
    end = start + safe_per_page
    return {
        "items": items[start:end],
        "page": safe_page,
        "per_page": safe_per_page,
        "total_items": total_items,
        "total_pages": total_pages,
        "has_previous": safe_page > 1,
        "has_next": safe_page < total_pages,
        "previous_page": safe_page - 1,
        "next_page": safe_page + 1,
    }
