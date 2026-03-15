from __future__ import annotations

from io import BytesIO

from starlette.datastructures import UploadFile
from starlette.requests import Request

from app.models.entities import ComparisonRun, ManualAPRAuditLog
from app.routers.comparisons import (
    comparison_detail,
    execute_comparison,
    execute_comparison_by_competencia,
)
from app.routers.divergences import divergences_page, export_divergences
from app.routers.history import history_page
from app.routers.imports import import_file
from app.routers.manual_aprs import (
    manual_apr_create,
    manual_apr_delete,
    manual_apr_delete_confirm,
    manual_apr_export_csv,
    manual_apr_import,
    manual_apr_import_csv,
    manual_apr_list,
)


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
            data_referencia="2026-03-01",
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
            data_referencia="2026-03-01",
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


def test_manual_apr_bulk_import_and_list_sorting(app_module):
    db = app_module.db_module.SessionLocal()
    try:
        response = manual_apr_import(
            make_request(app_module.app, method="POST", path="/manual-aprs/import"),
            import_text=(
                "apr_id;data_abertura;assunto;responsavel;status\n"
                "APR-30;11/03/2026 13:10;MANUTENCAO A;Maria;ativo\n"
                "APR-20;10/03/2026 09:00;MANUTENCAO B;Joao;ativo\n"
            ),
            db=db,
        )
        assert response.status_code == 303

        page = manual_apr_list(
            make_request(app_module.app, path="/manual-aprs"),
            q=None,
            sort="apr_id",
            direction="asc",
            page=1,
            db=db,
        )
        body = page.body.decode()
        assert page.status_code == 200
        assert "Importação manual em lote" in body
        assert "MANUTENCAO A" in body
        assert "MANUTENCAO B" in body
        assert body.index("APR-20") < body.index("APR-30")
    finally:
        db.close()


def test_manual_apr_csv_import_and_export(app_module):
    db = app_module.db_module.SessionLocal()
    try:
        import_response = manual_apr_import_csv(
            make_request(app_module.app, method="POST", path="/manual-aprs/import-csv"),
            arquivo=UploadFile(
                filename="base-manual.csv",
                file=BytesIO(
                    b"apr_id,data_abertura,assunto,responsavel,status\nAPR-40,2026-03-11,ASSUNTO CSV,Ana,ativo\n"
                ),
            ),
            db=db,
        )
        assert import_response.status_code == 303

        export_response = manual_apr_export_csv(q=None, sort="apr_id", direction="asc", db=db)
        assert export_response.status_code == 200
        assert "text/csv" in export_response.headers["content-type"]
        assert "base_manual_aprs.csv" in export_response.headers["content-disposition"]
    finally:
        db.close()


def test_manual_apr_delete_requires_confirmation_and_reruns_comparison(app_module):
    db = app_module.db_module.SessionLocal()
    try:
        create_response = manual_apr_create(
            make_request(app_module.app, method="POST", path="/manual-aprs"),
            apr_id="APR-55",
            data_referencia="2026-03-11",
            responsavel="Maria",
            descricao="ASSUNTO",
            observacao=None,
            status_apr="ativo",
            db=db,
        )
        assert create_response.status_code == 303

        import_response = import_file(
            make_request(app_module.app, method="POST", path="/imports"),
            competencia="2026-03",
            arquivo=UploadFile(
                filename="lote.csv",
                file=BytesIO(b"apr_id,descricao\nAPR-55,Conciliado\n"),
            ),
            db=db,
        )
        assert import_response.status_code == 303
        execute_comparison(
            make_request(app_module.app, method="POST", path="/comparisons/run/1"),
            batch_id=1,
            db=db,
        )

        confirm_page = manual_apr_delete_confirm(
            make_request(app_module.app, path="/manual-aprs/1/delete"),
            manual_apr_id=1,
            db=db,
        )
        assert confirm_page.status_code == 200
        assert "Digite o APR ID para confirmar" in confirm_page.body.decode()

        invalid_delete = manual_apr_delete(
            make_request(app_module.app, method="POST", path="/manual-aprs/1/delete"),
            manual_apr_id=1,
            confirm_apr_id="ERRADO",
            db=db,
        )
        assert invalid_delete.status_code == 400

        valid_delete = manual_apr_delete(
            make_request(app_module.app, method="POST", path="/manual-aprs/1/delete"),
            manual_apr_id=1,
            confirm_apr_id="APR-55",
            db=db,
        )
        assert valid_delete.status_code == 303

        runs = list(db.query(ComparisonRun).filter(ComparisonRun.batch_id == 1).order_by(ComparisonRun.id.asc()))
        delete_audit = db.query(ManualAPRAuditLog).filter_by(action="delete", apr_id="APR-55").one()
        assert len(runs) == 2
        assert runs[-1].total_manual == 0
        assert runs[-1].total_conciliado == 0
        assert runs[-1].total_faltando_manual == 1
        assert "apr_id=APR-55" in (delete_audit.detalhe or "")
    finally:
        db.close()


def test_import_run_comparison_and_export(app_module):
    db = app_module.db_module.SessionLocal()
    try:
        manual_apr_create(
            make_request(app_module.app, method="POST", path="/manual-aprs"),
            apr_id="APR-1",
            data_referencia="2026-03-01",
            responsavel="Equipe",
            descricao=None,
            observacao=None,
            status_apr="ativo",
            db=db,
        )
        manual_apr_create(
            make_request(app_module.app, method="POST", path="/manual-aprs"),
            apr_id="APR-9",
            data_referencia="2026-03-02",
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


def test_divergences_and_history_support_pagination(app_module):
    db = app_module.db_module.SessionLocal()
    try:
        manual_apr_create(
            make_request(app_module.app, method="POST", path="/manual-aprs"),
            apr_id="APR-1",
            data_referencia="2026-03-01",
            responsavel="Equipe",
            descricao=None,
            observacao=None,
            status_apr="ativo",
            db=db,
        )

        for index in range(25):
            response = import_file(
                make_request(app_module.app, method="POST", path="/imports"),
                competencia="2026-03",
                arquivo=UploadFile(
                    filename=f"lote-{index}.csv",
                    file=BytesIO(
                        f"ID,Assunto,Abertura\nAPR-X-{index},Assunto {index},11/03/2026 13:10\n".encode("utf-8")
                    ),
                ),
                db=db,
            )
            assert response.status_code == 303
            execute_comparison(
                make_request(app_module.app, method="POST", path=f"/comparisons/run/{index + 1}"),
                batch_id=index + 1,
                db=db,
            )

        divergences = divergences_page(
            make_request(app_module.app, path="/divergences"),
            competencia="2026-03",
            page=2,
            db=db,
        )
        assert divergences.status_code == 200
        divergences_body = divergences.body.decode()
        assert "Página 2 de" in divergences_body
        assert "Assunto" in divergences_body
        assert "Data de abertura" in divergences_body
        assert "11/03/2026" in divergences_body

        history = history_page(
            make_request(app_module.app, path="/history"),
            import_page=2,
            comparison_page=2,
            audit_page=1,
            db=db,
        )
        assert history.status_code == 200
        history_body = history.body.decode()
        assert "Página 2 de" in history_body
        assert "Auditoria Manual" in history_body
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
        assert run_before.scope_type == "batch"

        create_response = manual_apr_create(
            make_request(app_module.app, method="POST", path="/manual-aprs"),
            apr_id="APR-1",
            data_referencia="2026-03-10",
            responsavel="Maria",
            descricao=None,
            observacao=None,
            status_apr="ativo",
            db=db,
        )
        assert create_response.status_code == 303

        runs = list(db.query(ComparisonRun).filter(ComparisonRun.batch_id == 1).order_by(ComparisonRun.id.asc()))
        assert len(runs) == 2
        run_after = runs[-1]
        assert run_after.total_manual == 1
        assert run_after.total_conciliado == 1
        assert run_after.total_faltando_manual == 1
    finally:
        db.close()


def test_execute_comparison_by_competencia_creates_consolidated_run(app_module):
    db = app_module.db_module.SessionLocal()
    try:
        manual_apr_create(
            make_request(app_module.app, method="POST", path="/manual-aprs"),
            apr_id="APR-1",
            data_referencia="2026-03-01",
            responsavel="Equipe",
            descricao=None,
            observacao=None,
            status_apr="ativo",
            db=db,
        )

        for filename, content in (
            ("lote-a.csv", b"apr_id,descricao\nAPR-1,Conciliado\nAPR-2,Faltando manual\n"),
            ("lote-b.csv", b"apr_id,descricao\nAPR-2,Duplicado em lote diferente\nAPR-3,Novo\n"),
        ):
            response = import_file(
                make_request(app_module.app, method="POST", path="/imports"),
                competencia="2026-03",
                arquivo=UploadFile(filename=filename, file=BytesIO(content)),
                db=db,
            )
            assert response.status_code == 303

        comparison_response = execute_comparison_by_competencia(
            make_request(app_module.app, method="POST", path="/comparisons/run-by-competencia"),
            competencia="2026-03",
            db=db,
        )
        assert comparison_response.status_code == 303
        assert comparison_response.headers["location"] == "/comparisons/1"

        run = db.query(ComparisonRun).filter(ComparisonRun.id == 1).one()
        assert run.scope_type == "competencia"
        assert run.total_conciliado == 1
        assert run.total_faltando_manual == 1
        assert run.total_duplicados == 1
    finally:
        db.close()
