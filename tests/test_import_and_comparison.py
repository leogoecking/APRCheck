from __future__ import annotations

from app.schemas.forms import ImportBatchInput, ManualAPRInput
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
