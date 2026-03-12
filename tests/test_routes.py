from __future__ import annotations


def test_manual_apr_create_and_duplicate(client):
    response = client.post(
        "/manual-aprs",
        data={"apr_id": "APR-10", "responsavel": "Maria", "status": "ativo"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    duplicate = client.post(
        "/manual-aprs",
        data={"apr_id": "APR-10", "responsavel": "Joao", "status": "ativo"},
    )
    assert duplicate.status_code == 409
    assert "já existe" in duplicate.text


def test_import_run_comparison_and_export(client):
    client.post(
        "/manual-aprs",
        data={"apr_id": "APR-1", "responsavel": "Equipe", "status": "ativo"},
        follow_redirects=False,
    )
    client.post(
        "/manual-aprs",
        data={"apr_id": "APR-9", "responsavel": "Equipe", "status": "ativo"},
        follow_redirects=False,
    )
    files = {
        "arquivo": (
            "lote.csv",
            b"apr_id,descricao\nAPR-1,Conciliado\nAPR-2,Faltando manual\nAPR-2,Duplicado\nAPR-3,Faltando manual valido\n,Invalido\n",
            "text/csv",
        )
    }
    response = client.post(
        "/imports",
        data={"competencia": "2026-03"},
        files=files,
        follow_redirects=False,
    )
    assert response.status_code == 303
    batch_location = response.headers["location"]
    assert "batch_id=1" in batch_location

    comparison = client.post("/comparisons/run/1", follow_redirects=False)
    assert comparison.status_code == 303
    assert comparison.headers["location"] == "/comparisons/1"

    detail = client.get("/comparisons/1")
    assert detail.status_code == 200
    assert "faltando_no_manual" in detail.text
    assert "faltando_no_importado" in detail.text
    assert "duplicado" in detail.text
    assert "invalido" in detail.text

    divergences = client.get("/divergences?competencia=2026-03")
    assert divergences.status_code == 200
    assert "APR-1" not in divergences.text

    export = client.get("/divergences/export?competencia=2026-03")
    assert export.status_code == 200
    assert "text/csv" in export.headers["content-type"]
    assert "categoria" in export.text
