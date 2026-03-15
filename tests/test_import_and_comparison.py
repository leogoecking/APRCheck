from __future__ import annotations

from datetime import date
from pathlib import Path

from app.models.entities import ComparisonRun, ManualAPR, ManualAPRAuditLog
from app.schemas.forms import ImportBatchInput, ManualAPRInput
from app.services.comparison_service import (
    build_import_preview_map,
    extract_visual_fields,
    run_batch_comparison,
    run_competencia_comparison,
)
from app.services.import_service import create_import_batch, parse_csv_bytes, parse_xml_bytes
from app.services.manual_apr_service import create_manual_apr, import_manual_aprs_from_text


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def test_parse_csv_detects_alternate_header_and_duplicates():
    rows = parse_csv_bytes(
        b"ID APR,descricao\n APR-001 ,Primeiro\nAPR-002,Segundo\nAPR-002,Duplicado\n,Sem ID\n"
    )

    assert len(rows) == 4
    assert rows[0].apr_id == "APR-001"
    assert rows[0].is_valid is True
    assert rows[1].is_duplicate is True
    assert rows[1].is_valid is False
    assert rows[2].is_duplicate is True
    assert rows[3].error_message is not None


def test_parse_csv_accepts_semicolon_and_extended_header_aliases():
    rows = parse_csv_bytes(
        b"Codigo da APR;descricao\n APR-010 ;Primeiro\nAPR-011;Segundo\n"
    )

    assert len(rows) == 2
    assert rows[0].apr_id == "APR-010"
    assert rows[0].is_valid is True
    assert rows[1].apr_id == "APR-011"
    assert rows[1].is_valid is True


def test_parse_csv_accepts_tab_delimited_id_header():
    rows = parse_csv_bytes(
        (
            "ID\tAbertura\tAssunto\tColaborador\n"
            "238474\t11/03/2026 13:10\tMANUTENCAO CAIXA NAP\tHARISSON\n"
            "238470\t11/03/2026 12:24\tMANUTENCAO FIBRA\tHARISSON\n"
        ).encode("utf-8")
    )

    assert len(rows) == 2
    assert rows[0].apr_id == "238474"
    assert rows[0].is_valid is True
    assert rows[1].apr_id == "238470"
    assert rows[1].is_valid is True


def test_parse_csv_matches_real_mes03_sample_fixture():
    rows = parse_csv_bytes((FIXTURES_DIR / "real_mes03_sample.csv").read_bytes())

    assert len(rows) == 4
    assert rows[0].apr_id == "237673"
    assert rows[1].apr_id == "237674"
    assert rows[1].payload["Assunto"] == "MANUTENÇÃO CAIXA NAP"
    assert rows[3].payload["Colaborador"] == "HARISSON LUCAS CRUZ RESENDE"
    assert all(row.is_valid for row in rows)


def test_parse_csv_ignores_sep_and_preamble_before_real_header():
    rows = parse_csv_bytes(
        (
            "Relatorio de exportacao\n"
            "Gerado em 2026-03-11\n"
            "sep=;\n"
            "Numero da APR;Assunto;Abertura\n"
            "APR-900;MANUTENCAO;11/03/2026 13:10\n"
        ).encode("utf-8")
    )

    assert len(rows) == 1
    assert rows[0].apr_id == "APR-900"
    assert rows[0].is_valid is True


def test_extract_visual_fields_reads_assunto_and_open_date_without_time():
    preview = extract_visual_fields(
        '{"ID":"238474","Assunto":"MANUTENCAO CAIXA NAP","Abertura":"11/03/2026 13:10"}'
    )

    assert preview["assunto"] == "MANUTENCAO CAIXA NAP"
    assert preview["data_abertura"] == "11/03/2026"


def test_real_mes03_sample_generates_visual_preview_map(app_module):
    db = app_module.db_module.SessionLocal()
    try:
        batch = create_import_batch(
            db,
            type(
                "UploadStub",
                (),
                {
                    "filename": "Mes03.csv",
                    "file": type(
                        "FileStub",
                        (),
                        {"read": lambda self: (FIXTURES_DIR / "real_mes03_sample.csv").read_bytes()},
                    )(),
                },
            )(),
            ImportBatchInput(competencia="2026-03"),
        )

        preview_map = build_import_preview_map(batch.imported_aprs)

        assert preview_map["237673"]["assunto"] == "MANUTENCAO FIBRA - INFRA"
        assert preview_map["237673"]["data_abertura"] == "01/03/2026"
        assert preview_map["237746"]["assunto"] == "DOCUMENTAÇÃO FIBRA"
        assert preview_map["237746"]["data_abertura"] == "02/03/2026"
    finally:
        db.close()


def test_manual_bulk_import_accepts_structured_text_and_maps_visual_fields(app_module):
    db = app_module.db_module.SessionLocal()
    try:
        result = import_manual_aprs_from_text(
            db,
            "apr_id;data_abertura;assunto;responsavel;status\n"
            "APR-700;11/03/2026 13:10;MANUTENCAO;HARISSON;aberto\n",
        )

        assert result.created_count == 1
        manual = db.query(ManualAPR).filter_by(apr_id="APR-700").one()
        audit = db.query(ManualAPRAuditLog).filter_by(action="bulk_import").one()
        assert manual.descricao == "MANUTENCAO"
        assert str(manual.data_referencia) == "2026-03-11"
        assert "criadas=1" in (audit.detalhe or "")
    finally:
        db.close()


def test_parse_xml_detects_missing_id_and_duplicate():
    xml = b"""
    <root>
        <registro><apr_id>APR-100</apr_id><descricao>A</descricao></registro>
        <registro><apr_id>APR-100</apr_id><descricao>B</descricao></registro>
        <registro><descricao>Sem ID</descricao></registro>
    </root>
    """
    rows = parse_xml_bytes(xml)

    assert len(rows) == 3
    assert rows[0].is_duplicate is True
    assert rows[1].is_duplicate is True
    assert rows[2].is_valid is False


def test_parse_xml_accepts_attribute_and_nested_id_fields():
    xml = b"""
    <root>
        <registro apr_id="APR-200"><descricao>A</descricao></registro>
        <registro><dados><apr_id>APR-201</apr_id></dados><descricao>B</descricao></registro>
    </root>
    """
    rows = parse_xml_bytes(xml)

    assert len(rows) == 2
    assert rows[0].apr_id == "APR-200"
    assert rows[0].is_valid is True
    assert rows[1].apr_id == "APR-201"
    assert rows[1].is_valid is True


def test_parse_xml_detects_repeated_records_in_nested_collection():
    xml = b"""
    <retorno>
        <lote>
            <registros>
                <item><numero_da_apr>APR-301</numero_da_apr><assunto>A</assunto></item>
                <item><numero_da_apr>APR-302</numero_da_apr><assunto>B</assunto></item>
            </registros>
        </lote>
    </retorno>
    """
    rows = parse_xml_bytes(xml)

    assert len(rows) == 2
    assert rows[0].apr_id == "APR-301"
    assert rows[1].apr_id == "APR-302"


def test_batch_comparison_uses_only_apr_id(app_module):
    db = app_module.db_module.SessionLocal()
    try:
        create_manual_apr(
            db,
            ManualAPRInput(
                apr_id="APR-001",
                data_referencia=date(2026, 3, 10),
                responsavel="Equipe A",
                descricao="Manual",
                status="aberto",
            ),
        )
        create_manual_apr(
            db,
            ManualAPRInput(
                apr_id="APR-003",
                data_referencia=date(2026, 3, 11),
                responsavel="Equipe B",
                descricao="Outro",
                status="fechado",
            ),
        )
        batch = create_import_batch(
            db,
            type(
                "UploadStub",
                (),
                {"filename": "lote.csv", "file": type("FileStub", (), {"read": lambda self: b"apr_id,descricao\nAPR-001,Descricao diferente\nAPR-002,Novo\n"})()},
            )(),
            ImportBatchInput(competencia="2026-03"),
        )

        result = run_batch_comparison(db, batch.id)

        assert result is not None
        assert result.total_conciliado == 1
        assert result.total_faltando_manual == 1
        assert result.total_faltando_importado == 1
    finally:
        db.close()


def test_manual_create_generates_audit_log(app_module):
    db = app_module.db_module.SessionLocal()
    try:
        create_manual_apr(
            db,
            ManualAPRInput(
                apr_id="APR-AUDIT-1",
                data_referencia=date(2026, 3, 12),
                descricao="Teste",
            ),
        )

        audit = db.query(ManualAPRAuditLog).filter_by(action="create", apr_id="APR-AUDIT-1").one()
        assert audit.competencia == "2026-03"
        assert "assunto=Teste" in (audit.detalhe or "")
    finally:
        db.close()


def test_create_import_batch_accepts_tsv_extension(app_module):
    db = app_module.db_module.SessionLocal()
    try:
        batch = create_import_batch(
            db,
            type(
                "UploadStub",
                (),
                {
                    "filename": "lote.tsv",
                    "file": type(
                        "FileStub",
                        (),
                        {"read": lambda self: b"ID\tAbertura\tAssunto\n238474\t11/03/2026 13:10\tMANUTENCAO\n"},
                    )(),
                },
            )(),
            ImportBatchInput(competencia="2026-03"),
        )

        assert batch.tipo_arquivo == "tsv"
        assert batch.total_registros == 1
        assert batch.total_validos == 1
    finally:
        db.close()


def test_batch_comparison_preserves_history_for_same_batch(app_module):
    db = app_module.db_module.SessionLocal()
    try:
        create_manual_apr(
            db,
            ManualAPRInput(
                apr_id="APR-001",
                data_referencia=date(2026, 3, 1),
                responsavel="Equipe A",
            ),
        )
        batch = create_import_batch(
            db,
            type(
                "UploadStub",
                (),
                {
                    "filename": "lote.csv",
                    "file": type(
                        "FileStub",
                        (),
                        {"read": lambda self: b"apr_id,descricao\nAPR-001,Conciliado\nAPR-002,Novo\n"},
                    )(),
                },
            )(),
            ImportBatchInput(competencia="2026-03"),
        )

        first_run = run_batch_comparison(db, batch.id)
        second_run = run_batch_comparison(db, batch.id)

        assert first_run is not None
        assert second_run is not None
        runs = list(db.query(ComparisonRun).filter(ComparisonRun.batch_id == batch.id))
        assert len(runs) == 2
        assert runs[-1].id == second_run.id
    finally:
        db.close()


def test_competencia_comparison_combines_batches_and_detects_cross_batch_duplicates(app_module):
    db = app_module.db_module.SessionLocal()
    try:
        create_manual_apr(
            db,
            ManualAPRInput(
                apr_id="APR-001",
                data_referencia=date(2026, 3, 2),
                responsavel="Equipe A",
            ),
        )
        create_manual_apr(
            db,
            ManualAPRInput(
                apr_id="APR-003",
                data_referencia=date(2026, 3, 3),
                responsavel="Equipe B",
            ),
        )

        create_import_batch(
            db,
            type(
                "UploadStub",
                (),
                {
                    "filename": "lote-a.csv",
                    "file": type(
                        "FileStub",
                        (),
                        {"read": lambda self: b"apr_id,descricao\nAPR-001,Conciliado\nAPR-002,Primeiro\n"},
                    )(),
                },
            )(),
            ImportBatchInput(competencia="2026-03"),
        )
        create_import_batch(
            db,
            type(
                "UploadStub",
                (),
                {
                    "filename": "lote-b.csv",
                    "file": type(
                        "FileStub",
                        (),
                        {"read": lambda self: b"apr_id,descricao\nAPR-002,Duplicado em outro lote\nAPR-004,Novo\n"},
                    )(),
                },
            )(),
            ImportBatchInput(competencia="2026-03"),
        )

        result = run_competencia_comparison(db, "2026-03")

        assert result is not None
        assert result.scope_type == "competencia"
        assert result.scope_value == "2026-03"
        assert result.total_manual == 2
        assert result.total_importado == 2
        assert result.total_conciliado == 1
        assert result.total_faltando_manual == 1
        assert result.total_faltando_importado == 1
        assert result.total_duplicados == 1
    finally:
        db.close()
