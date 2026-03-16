# 03 - Priorização

```json
{
  "id": "BUG-001",
  "tipo": "bug_reproduzivel",
  "severidade": "media",
  "confianca": "alta",
  "arquivo": "app/main.py",
  "sintoma": "Mensagens flash de sucesso/erro nao aparecem apos redirects.",
  "causa_raiz": "A aplicacao usa set_flash/pop_flash baseados em sessao, mas nao registra SessionMiddleware.",
  "evidencia": [
    "app.user_middleware retornou []",
    "app/utils/web.py encerra cedo se request.scope nao tiver session",
    "base.html depende de flash para exibir alertas"
  ],
  "correcao_recomendada": "Adicionar SessionMiddleware com secret_key configurada e validar o fluxo de redirect com teste HTTP.",
  "corrigir_agora": true
}
```

```json
{
  "id": "BUG-002",
  "tipo": "bug_reproduzivel",
  "severidade": "alta",
  "confianca": "alta",
  "arquivo": "app/schemas/forms.py",
  "sintoma": "Competencias fora do formato YYYY-MM geram comparacoes por competencia com total_manual=0 mesmo havendo APR manual no mesmo mes.",
  "causa_raiz": "A validacao de competencia aceita texto livre, enquanto a carga manual e comparada usando strftime('%Y-%m').",
  "evidencia": [
    "ImportBatchInput apenas aplica strip()",
    "comparison_service._load_manual_ids_for_competencia compara contra YYYY-MM",
    "reproducao isolada retornou run_total_manual 0, run_total_conciliado 0 e run_total_faltando_manual 1 para APR-900"
  ],
  "correcao_recomendada": "Validar e padronizar competencia no formato YYYY-MM na entrada e manter esse formato em toda a aplicacao.",
  "corrigir_agora": true
}
```

```json
{
  "id": "BUG-003",
  "tipo": "bug_reproduzivel",
  "severidade": "alta",
  "confianca": "alta",
  "arquivo": "app/models/entities.py",
  "sintoma": "Excluir um lote apaga tambem imported_aprs e comparison_runs, eliminando historico que deveria ser persistido.",
  "causa_raiz": "As relacoes de ImportBatch usam cascade='all, delete-orphan' e delete_import_batch executa exclusao fisica do lote.",
  "evidencia": [
    "models.entities.ImportBatch define cascata para imported_aprs e comparison_runs",
    "import_service.delete_import_batch faz db.delete(batch)",
    "reproducao isolada mostrou before_batches 1 before_runs 1 e after_batches 0 after_runs 0"
  ],
  "correcao_recomendada": "Trocar exclusao fisica por desativacao logica, ou bloquear exclusao apos uso em comparacoes, preservando auditoria e historico.",
  "corrigir_agora": true
}
```

```json
{
  "id": "RISK-001",
  "tipo": "problema_de_qualidade",
  "severidade": "media",
  "confianca": "alta",
  "arquivo": "app/routers/history.py",
  "sintoma": "Listagens e filtros materializam colecoes inteiras antes da paginacao.",
  "causa_raiz": "A paginacao eh feita em Python sobre listas completas, em vez de LIMIT/OFFSET no banco.",
  "evidencia": [
    "manual_apr_list usa list_manual_aprs(...) e depois paginate(...)",
    "divergences_page usa list_divergence_items(...) e depois paginate(...)",
    "history_page carrega batches/comparisons/audits completos antes da paginacao"
  ],
  "correcao_recomendada": "Mover ordenacao, filtros e paginacao para queries SQLAlchemy.",
  "corrigir_agora": false
}
```
