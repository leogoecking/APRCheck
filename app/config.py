from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
TEMPLATES_DIR = BASE_DIR / "app" / "templates"
STATIC_DIR = BASE_DIR / "app" / "static"


@dataclass(slots=True)
class Settings:
    app_name: str = "Conciliador de APR"
    secret_key: str = os.getenv("APP_SECRET_KEY", "apr-conciliador-dev-key")
    database_url: str = os.getenv(
        "APP_DATABASE_URL",
        f"sqlite:///{(DATA_DIR / 'app.db').as_posix()}",
    )
    templates_dir: Path = TEMPLATES_DIR
    static_dir: Path = STATIC_DIR


settings = Settings()
