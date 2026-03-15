from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import DATA_DIR, settings


class Base(DeclarativeBase):
    pass


connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def init_db() -> None:
    from app.models import entities  # noqa: F401

    ensure_data_dir()
    Base.metadata.create_all(bind=engine)
    _apply_sqlite_compat_migrations()


def _apply_sqlite_compat_migrations() -> None:
    if not settings.database_url.startswith("sqlite"):
        return

    with engine.begin() as connection:
        inspector = inspect(connection)
        if "comparison_runs" not in inspector.get_table_names():
            return

        columns = {column["name"] for column in inspector.get_columns("comparison_runs")}
        if "scope_type" not in columns:
            connection.execute(
                text(
                    "ALTER TABLE comparison_runs "
                    "ADD COLUMN scope_type VARCHAR(20) NOT NULL DEFAULT 'batch'"
                )
            )
        if "scope_value" not in columns:
            connection.execute(
                text(
                    "ALTER TABLE comparison_runs "
                    "ADD COLUMN scope_value VARCHAR(120) NOT NULL DEFAULT ''"
                )
            )
            connection.execute(
                text(
                    "UPDATE comparison_runs "
                    "SET scope_value = CASE "
                    "WHEN scope_type = 'competencia' THEN competencia "
                    "ELSE CAST(batch_id AS TEXT) "
                    "END "
                    "WHERE scope_value = ''"
                )
            )
        if "source_batch_ids" not in columns:
            connection.execute(
                text("ALTER TABLE comparison_runs ADD COLUMN source_batch_ids TEXT")
            )
            connection.execute(
                text(
                    "UPDATE comparison_runs "
                    "SET source_batch_ids = CAST(batch_id AS TEXT) "
                    "WHERE source_batch_ids IS NULL"
                )
            )

        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_comparison_runs_scope "
                "ON comparison_runs (scope_type, scope_value, created_at)"
            )
        )


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
