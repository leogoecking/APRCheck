from __future__ import annotations

import os
from types import SimpleNamespace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def app_module(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    database_file = tmp_path / "test.db"
    monkeypatch.setenv("APP_DATABASE_URL", f"sqlite:///{database_file.as_posix()}")
    monkeypatch.setenv("APP_SECRET_KEY", "test-secret")

    import app.config as config_module
    import app.db as db_module
    import app.main as main_module

    config_module.settings.database_url = os.environ["APP_DATABASE_URL"]
    config_module.settings.secret_key = os.environ["APP_SECRET_KEY"]
    db_module.engine.dispose()
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    db_module.engine = create_engine(
        config_module.settings.database_url,
        connect_args={"check_same_thread": False},
        future=True,
    )
    db_module.SessionLocal = sessionmaker(
        bind=db_module.engine,
        autoflush=False,
        autocommit=False,
        future=True,
    )
    db_module.init_db()
    main_module.app = main_module.create_app()
    return SimpleNamespace(app=main_module.app, db_module=db_module)


@pytest.fixture
def client(app_module):
    with TestClient(app_module.app) as test_client:
        yield test_client
