# 02 - Achados

## Contexto desta rodada

- Objetivo: analisar o código com base no fluxo exigido em `AGENTS.md`, sem assumir bugs sem evidência.
- Validação ampla executada: `.venv/bin/pytest -q`
- Resultado da suíte: `34 passed in 30.30s`
- Conclusão parcial: a suíte atual está verde, então os achados desta rodada vieram de inspeção dirigida e reprodução isolada.

## BUG-007

- Tipo: `bug_reproduzivel`
- Método:
  - inspeção de `app/routers/history.py`
  - inspeção de `app/templates/history/index.html`
  - reprodução em banco temporário via chamada direta das rotas `import_file`, `import_batch_delete` e `history_page`
- Comando/reprodução:

```bash
mkdir -p /tmp/aprcheck-analysis-history && .venv/bin/python - <<'PY'
from io import BytesIO
from pathlib import Path
from _pytest.monkeypatch import MonkeyPatch
from starlette.datastructures import UploadFile

from app.routers.history import history_page
from app.routers.imports import import_batch_delete, import_file
from tests.conftest import app_module as fixture_func
from tests.test_routes import make_request

mp = MonkeyPatch()
ctx = fixture_func.__wrapped__(Path('/tmp/aprcheck-analysis-history'), mp)
db = ctx.db_module.SessionLocal()
try:
    resp = import_file(
        make_request(ctx.app, method='POST', path='/imports'),
        competencia='2026-03',
        arquivo=UploadFile(filename='lote.csv', file=BytesIO(b'apr_id,descricao\nAPR-1,Teste\n')),
        db=db,
    )
    print('import_status', resp.status_code)
    delete_resp = import_batch_delete(
        make_request(ctx.app, method='POST', path='/imports/1/delete'),
        batch_id=1,
        confirm_batch_id='1',
        db=db,
    )
    print('delete_status', delete_resp.status_code)
    page = history_page(make_request(ctx.app, path='/history'), db=db)
    body = page.body.decode()
    print('history_status', page.status_code)
    print('contains_batch_1', '#1' in body)
    print('contains_file', 'lote.csv' in body)
    print('contains_empty_msg', 'Nenhuma importação registrada.' in body)
finally:
    db.close()
    mp.undo()
PY
```

- Saída observada:
  - `import_status 303`
  - `delete_status 303`
  - `history_status 200`
  - `contains_batch_1 True`
  - `contains_file True`
  - `contains_empty_msg False`
- Impacto:
  - um lote excluído logicamente continua visível na tela de histórico
  - isso contradiz o fluxo operacional da exclusão lógica, que remove o lote da área operacional e deveria evitar confusão sobre o que ainda está ativo
- Por que isso é evidência:
  - `history_page()` busca `ImportBatch` sem filtro por `deleted_at`
  - o template `app/templates/history/index.html` renderiza diretamente a lista `batches`
  - a reprodução confirmou que o lote continua aparecendo após `delete_import_batch()`
- Arquivos afetados:
  - `app/routers/history.py`
  - `app/templates/history/index.html`
- Reprodução: bem-sucedida
- Confiança: alta

## RISK-001

- Tipo: `risco_potencial`
- Método:
  - inspeção de `app/config.py`
  - leitura do valor efetivo de `settings.secret_key` sem variável de ambiente
- Comando:

```bash
.venv/bin/python - <<'PY'
from app.config import settings
print('secret_key', settings.secret_key)
print('uses_default', settings.secret_key == 'apr-conciliador-dev-key')
PY
```

- Saída observada:
  - `secret_key apr-conciliador-dev-key`
  - `uses_default True`
- Impacto:
  - se a aplicação for exposta em rede sem sobrescrever `APP_SECRET_KEY`, a sessão assinada pode ficar previsível
  - isso pode permitir falsificação de cookie de sessão e mensagens flash, dependendo da superfície exposta
- Por que isso ainda não é vulnerabilidade confirmada:
  - o sistema atual não implementa autenticação/autorização
  - a análise não confirmou exploração prática em um ambiente exposto real
  - portanto, há evidência de configuração fraca, mas não de impacto explorado no contexto real
- Arquivos afetados:
  - `app/config.py`
  - `app/main.py`
- Reprodução: parcialmente bem-sucedida
  - foi confirmada a configuração previsível
  - não foi confirmada exploração no contexto real
- Confiança: média
