from __future__ import annotations

from datetime import date

from starlette.requests import Request


def set_flash(request: Request, level: str, message: str) -> None:
    request.session["_flash"] = {"level": level, "message": message}


def pop_flash(request: Request) -> dict[str, str] | None:
    return request.session.pop("_flash", None)


def parse_optional_date(value: str | None) -> date | None:
    if not value:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    return date.fromisoformat(cleaned)
