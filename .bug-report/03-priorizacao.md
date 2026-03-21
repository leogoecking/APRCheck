# 03 - Priorização

```json
{
  "id": "BUG-007",
  "tipo": "bug_reproduzivel",
  "severidade": "media",
  "confianca": "alta",
  "arquivo": "app/routers/history.py",
  "sintoma": "Um lote importado continua aparecendo na tela de historico mesmo depois da exclusao logica.",
  "causa_raiz": "A consulta de history_page lista ImportBatch sem filtrar deleted_at IS NULL, entao a exclusao logica nao e respeitada na visao de historico.",
  "evidencia": [
    "reproducao isolada retornou delete_status 303 e depois contains_batch_1 True",
    "history_page faz select(ImportBatch) sem filtro por deleted_at",
    "app/templates/history/index.html renderiza batches sem distinguir lote excluido"
  ],
  "correcao_recomendada": "Aplicar filtro por deleted_at IS NULL na listagem de importacoes do historico, ou sinalizar explicitamente o status excluido se a intencao for auditoria completa.",
  "corrigir_agora": false
}
```

```json
{
  "id": "RISK-001",
  "tipo": "risco_potencial",
  "severidade": "media",
  "confianca": "media",
  "arquivo": "app/config.py",
  "sintoma": "A aplicacao usa uma secret_key previsivel quando APP_SECRET_KEY nao esta definida.",
  "causa_raiz": "Settings.secret_key cai para o valor fixo 'apr-conciliador-dev-key', que e adequado apenas para desenvolvimento controlado.",
  "evidencia": [
    "app/config.py define os.getenv('APP_SECRET_KEY', 'apr-conciliador-dev-key')",
    "execucao local confirmou uses_default True"
  ],
  "correcao_recomendada": "Falhar em ambientes nao-desenvolvimento sem APP_SECRET_KEY definida, ou gerar chave obrigatoria por configuracao de deploy e documentar isso no bootstrap.",
  "corrigir_agora": false
}
```
