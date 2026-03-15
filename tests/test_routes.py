from __future__ import annotations

from io import BytesIO

from starlette.datastructures import UploadFile
from starlette.requests import Request

from app.models.entities import ComparisonRun
from app.routers.comparisons import comparison_detail, execute_comparison
from app.routers.divergences import divergences_page, export_divergences
from app.routers.imports import import_file
from app.routers.manual_aprs import manual_apr_create


def make_request(app, method: str = "GET", path: str = "/") -> Request:
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": method,
            "scheme": "http",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": [],
            "client": ("testclient", 50000),
            "server": ("testserver", 80),
            "app": app,
        }
    )


def test_manual_apr_create_and_duplicate(app_module):
    db = app_module.db_module.SessionLocal()
    try:
        response = manual_apr_create(
            make_request(app_module.app, method="POST", path="/manual-aprs"),
            apr_id="APR-10",
            data_referencia=None,
            responsavel="Maria",
            descricao=None,
            observacao=None,
            status_apr="ativo",
            db=db,
        )
        assert response.status_code == 303

        duplicate = manual_apr_create(
            make_request(app_module.app, method="POST", path="/manual-aprs"),
            apr_id="APR-10",
            data_referencia=None,
            responsavel="Joao",
            descricao=None,
            observacao=None,
            status_apr="ativo",
            db=db,
        )
        assert duplicate.status_code == 409
        assert "já existe" in duplicate.body.decode()
    finally:
        db.close()


def test_import_run_comparison_and_export(app_module):
    db = app_module.db_module.SessionLocal()
    try:
        manual_apr_create(
            make_request(app_module.app, method="POST", path="/manual-aprs"),
            apr_id="APR-1",
            data_referencia=None,
            responsavel="Equipe",
            descricao=None,
            observacao=None,
            status_apr="ativo",
            db=db,
        )
        manual_apr_create(
            make_request(app_module.app, method="POST", path="/manual-aprs"),
            apr_id="APR-9",
            data_referencia=None,
            responsavel="Equipe",
            descricao=None,
            observacao=None,
            status_apr="ativo",
            db=db,
        )

        upload = UploadFile(
            filename="lote.csv",
            file=BytesIO(
                b"apr_id,descricao\nAPR-1,Conciliado\nAPR-2,Faltando manual\nAPR-2,Duplicado\nAPR-3,Faltando manual valido\n,Invalido\n"
            ),
        )
        response = import_file(
            make_request(app_module.app, method="POST", path="/imports"),
            competencia="2026-03",
            arquivo=upload,
            db=db,
        )
        assert response.status_code == 303
        assert "batch_id=1" in response.headers["location"]

        comparison = execute_comparison(
            make_request(app_module.app, method="POST", path="/comparisons/run/1"),
            batch_id=1,
            db=db,
        )
        assert comparison.status_code == 303
        assert comparison.headers["location"] == "/comparisons/1"

        detail = comparison_detail(
            make_request(app_module.app, path="/comparisons/1"),
            run_id=1,
            db=db,
        )
        assert detail.status_code == 200
        detail_body = detail.body.decode()
        assert "faltando_no_manual" in detail_body
        assert "faltando_no_importado" in detail_body
        assert "duplicado" in detail_body
        assert "invalido" in detail_body

        divergences = divergences_page(
            make_request(app_module.app, path="/divergences"),
            competencia="2026-03",
            db=db,
        )
        assert divergences.status_code == 200
        assert "APR-1" not in divergences.body.decode()

        export = export_divergences(competencia="2026-03", db=db)
        assert export.status_code == 200
        assert "text/csv" in export.headers["content-type"]
        assert "divergencias.csv" in export.headers["content-disposition"]
    finally:
        db.close()


def test_manual_apr_create_reruns_existing_comparisons(app_module):
    db = app_module.db_module.SessionLocal()
    try:
        upload = UploadFile(
            filename="lote.csv",
            file=BytesIO(b"apr_id,descricao\nAPR-1,Conciliado\nAPR-2,Faltando manual\n"),
        )
        import_response = import_file(
            make_request(app_module.app, method="POST", path="/imports"),
            competencia="2026-03",
            arquivo=upload,
            db=db,
        )
        assert import_response.status_code == 303

        comparison_response = execute_comparison(
            make_request(app_module.app, method="POST", path="/comparisons/run/1"),
            batch_id=1,
            db=db,
        )
        assert comparison_response.status_code == 303

        run_before = db.query(ComparisonRun).filter(ComparisonRun.batch_id == 1).one()
        assert run_before.total_manual == 0
        assert run_before.total_conciliado == 0
        assert run_before.total_faltando_manual == 2

        create_response = manual_apr_create(
            make_request(app_module.app, method="POST", path="/manual-aprs"),
            apr_id="APR-1",
            data_referencia=None,
            responsavel="Maria",
            descricao=None,
            observacao=None,
            status_apr="ativo",
            db=db,
        )
        assert create_response.status_code == 303

        run_after = db.query(ComparisonRun).filter(ComparisonRun.batch_id == 1).one()
        assert run_after.total_manual == 1
        assert run_after.total_conciliado == 1
        assert run_after.total_faltando_manual == 1
    finally:
        db.close()
