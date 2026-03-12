from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.db import init_db
from app.routers import comparisons, dashboard, divergences, history, imports, manual_aprs


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)
    app.state.templates = Jinja2Templates(directory=str(settings.templates_dir))
    app.mount("/static", StaticFiles(directory=str(settings.static_dir)), name="static")

    app.include_router(dashboard.router)
    app.include_router(manual_aprs.router)
    app.include_router(imports.router)
    app.include_router(comparisons.router)
    app.include_router(divergences.router)
    app.include_router(history.router)
    return app


app = create_app()
