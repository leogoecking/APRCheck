# 02 - Achados

## BUG-001

- Tipo: `bug_reproduzivel`
- Método:
  - inspeção de `app/main.py`, `app/utils/web.py` e `app/templates/base.html`
  - comando executado: `.venv/bin/python -c "from app.main import create_app; app=create_app(); print(app.user_middleware)"`
- Saída/observação:
  - `app.user_middleware` retornou `[]`
  - `set_flash()` e `pop_flash()` retornam sem efeito quando `"session"` não existe no `request.scope`
  - o template base renderiza alertas apenas a partir de `flash`
- Impacto:
  - mensagens de sucesso após redirects nunca chegam ao usuário
  - o projeto promete feedback visual claro, mas o fluxo real perde confirmações como cadastro/importação/conciliação bem-sucedidos
- Por que isso é evidência:
  - as rotas chamam `set_flash(...)`, porém a aplicação não registra `SessionMiddleware`
  - sem middleware de sessão, `request.session` não existe e o utilitário sai silenciosamente
- Arquivos afetados:
  - `app/main.py`
  - `app/utils/web.py`
  - `app/templates/base.html`
- Reprodução: bem-sucedida por inspeção + verificação objetiva do middleware
- Confiança: alta

## BUG-002

- Tipo: `bug_reproduzivel`
- Método:
  - comando executado em banco temporário:
    - `APP_DATABASE_URL=sqlite:////tmp/aprcheck_comp_test.db .venv/bin/python -c "... ImportBatchInput(competencia='03/2026') ... run_competencia_comparison(db, '03/2026') ..."`
- Saída observada:
  - `run_total_manual 0`
  - `run_total_conciliado 0`
  - `run_total_faltando_manual 1`
- Impacto:
  - um lote com competência em formato livre gera divergência falsa, mesmo quando o `apr_id` existe manualmente no mesmo mês
  - isso compromete a conciliação por competência e o dashboard/histórico derivados dela
- Por que isso é evidência:
  - `ImportBatchInput` apenas faz `strip()`
  - `_load_manual_ids_for_competencia()` compara a competência contra `strftime("%Y-%m", ManualAPR.data_referencia)`
  - qualquer formato fora de `YYYY-MM` quebra a correspondência
- Arquivos afetados:
  - `app/schemas/forms.py`
  - `app/services/comparison_service.py`
- Reprodução: bem-sucedida
- Confiança: alta

## BUG-003

- Tipo: `bug_reproduzivel`
- Método:
  - inspeção de `app/models/entities.py` e `app/services/import_service.py`
  - comando executado em banco temporário:
    - `APP_DATABASE_URL=sqlite:////tmp/aprcheck_history_test.db .venv/bin/python -c "... run_batch_comparison(db, batch.id) ... delete_import_batch(db, batch) ..."`
- Saída observada:
  - `before_batches 1 before_runs 1`
  - `after_batches 0 after_runs 0`
- Impacto:
  - excluir um lote remove também os registros importados e todo o histórico de comparação associado
  - isso contradiz a exigência funcional de manter histórico de importações e execuções de comparação
- Por que isso é evidência:
  - `ImportBatch.imported_aprs` e `ImportBatch.comparison_runs` usam `cascade="all, delete-orphan"`
  - `delete_import_batch()` faz `db.delete(batch)` e `commit()`
  - a remoção foi confirmada em execução isolada
- Arquivos afetados:
  - `app/models/entities.py`
  - `app/services/import_service.py`
- Reprodução: bem-sucedida
- Confiança: alta

## RISK-001

- Tipo: `problema_de_qualidade`
- Método:
  - inspeção de `app/routers/history.py`, `app/routers/divergences.py`, `app/routers/manual_aprs.py`
- Observação:
  - as listagens carregam todos os registros em memória e só depois paginam com `paginate(...)`
- Impacto:
  - com crescimento de lotes, comparações e divergências, a latência e o consumo de memória tendem a subir de forma desnecessária
- Por que isso é evidência:
  - `list(...)`/`db.scalars(...)` materializam coleções inteiras antes da paginação
  - a paginação atual é puramente em Python, não no banco
- Arquivos afetados:
  - `app/routers/history.py`
  - `app/routers/divergences.py`
  - `app/routers/manual_aprs.py`
- Reprodução:
  - não houve falha funcional imediata na base de teste; trata-se de fragilidade estrutural confirmada por inspeção
- Confiança: alta
