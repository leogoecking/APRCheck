from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import DATA_DIR, settings
from app.services.apr_utils import normalize_competencia


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

        batch_columns = {column["name"] for column in inspector.get_columns("import_batches")}
        if "deleted_at" not in batch_columns:
            connection.execute(
                text("ALTER TABLE import_batches ADD COLUMN deleted_at DATETIME")
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_import_batches_deleted_at "
                    "ON import_batches (deleted_at)"
                )
            )

        _normalize_competencia_columns(connection, inspector)


def _normalize_competencia_columns(connection, inspector) -> None:
    if "import_batches" in inspector.get_table_names():
        rows = connection.execute(text("SELECT id, competencia FROM import_batches")).mappings().all()
        for row in rows:
            normalized = normalize_competencia(row["competencia"])
            if normalized and normalized != row["competencia"]:
                connection.execute(
                    text("UPDATE import_batches SET competencia = :competencia WHERE id = :id"),
                    {"competencia": normalized, "id": row["id"]},
                )

    if "comparison_runs" in inspector.get_table_names():
        rows = connection.execute(
            text("SELECT id, competencia, scope_type, scope_value FROM comparison_runs")
        ).mappings().all()
        for row in rows:
            normalized = normalize_competencia(row["competencia"])
            if normalized and normalized != row["competencia"]:
                connection.execute(
                    text("UPDATE comparison_runs SET competencia = :competencia WHERE id = :id"),
                    {"competencia": normalized, "id": row["id"]},
                )

            if row["scope_type"] == "competencia":
                normalized_scope = normalize_competencia(row["scope_value"])
                if normalized_scope and normalized_scope != row["scope_value"]:
                    connection.execute(
                        text("UPDATE comparison_runs SET scope_value = :scope_value WHERE id = :id"),
                        {"scope_value": normalized_scope, "id": row["id"]},
                    )


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
