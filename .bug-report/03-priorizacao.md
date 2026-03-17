# 03 - Priorização

```json
{
  "id": "BUG-004",
  "tipo": "bug_reproduzivel",
  "severidade": "alta",
  "confianca": "alta",
  "arquivo": "app/routers/comparisons.py",
  "sintoma": "O endpoint de comparacao por lote continua ativo e gera ComparisonRun com scope_type='batch', apesar do fluxo operacional atual ser mensal.",
  "causa_raiz": "A interface foi migrada para comparacao mensal, mas a rota POST /comparisons/run/{batch_id} e a logica associada continuam expostas sem bloqueio.",
  "evidencia": [
    "inspecao do endpoint em app/routers/comparisons.py",
    "reproducao isolada retornou status 303",
    "a execucao criada ficou com scope_type 'batch' e scope_value '1'"
  ],
  "correcao_recomendada": "Bloquear ou remover a execucao operacional por lote, mantendo apenas comparacao por competencia para novas execucoes.",
  "corrigir_agora": true
}
```

```json
{
  "id": "BUG-005",
  "tipo": "bug_reproduzivel",
  "severidade": "alta",
  "confianca": "alta",
  "arquivo": "app/services/dashboard_service.py",
  "sintoma": "Uma comparacao por lote ainda pode ser criada, mas depois nao aparece no dashboard nem no historico principal.",
  "causa_raiz": "Dashboard e historico filtram apenas scope_type='competencia', enquanto o endpoint legado ainda permite criar novas comparacoes batch.",
  "evidencia": [
    "dashboard_service seleciona apenas ComparisonRun.scope_type == 'competencia'",
    "history_page filtra comparacoes por scope_type == 'competencia'",
    "reproducao isolada mostrou dashboard_latest_run_is_none True e history_shows_no_comparisons True apos criar batch run"
  ],
  "correcao_recomendada": "Eliminar a geracao de batch runs novos ou, se a rota precisar permanecer, exibir explicitamente essas execucoes no dashboard/historico.",
  "corrigir_agora": true
}
```
