from __future__ import annotations

from app.schemas.forms import ImportBatchInput, ManualAPRInput
from app.models.entities import ComparisonRun
from app.services.comparison_service import run_comparison
from app.services.import_service import create_import_batch, parse_csv_bytes, parse_xml_bytes
from app.services.manual_apr_service import create_manual_apr


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


def test_comparison_uses_only_apr_id(app_module):
    db = app_module.db_module.SessionLocal()
    try:
        create_manual_apr(
            db,
            ManualAPRInput(
                apr_id="APR-001",
                responsavel="Equipe A",
                descricao="Manual",
                status="aberto",
            ),
        )
        create_manual_apr(
            db,
            ManualAPRInput(
                apr_id="APR-003",
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

        result = run_comparison(db, batch.id)

        assert result is not None
        assert result.total_conciliado == 1
        assert result.total_faltando_manual == 1
        assert result.total_faltando_importado == 1
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


def test_run_comparison_replaces_previous_run_for_same_batch(app_module):
    db = app_module.db_module.SessionLocal()
    try:
        create_manual_apr(
            db,
            ManualAPRInput(
                apr_id="APR-001",
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

        first_run = run_comparison(db, batch.id)
        second_run = run_comparison(db, batch.id)

        assert first_run is not None
        assert second_run is not None
        runs = list(db.query(ComparisonRun).filter(ComparisonRun.batch_id == batch.id))
        assert len(runs) == 1
        assert runs[0].id == second_run.id
    finally:
        db.close()
