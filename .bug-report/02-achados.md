# 02 - Achados

## Contexto desta rodada

- Comando executado: `.venv/bin/pytest`
- Resultado observado: `32 passed in 3.35s`
- Leitura adicional focada em fluxos alterados recentemente:
  - comparação mensal
  - dashboard
  - histórico
  - cadastro manual

## BUG-004

- Tipo: `bug_reproduzivel`
- Método:
  - inspeção de `app/routers/comparisons.py`
  - reprodução em banco temporário com chamada direta de `POST /comparisons/run/{batch_id}`
- Saída observada:
  - `status 303`
  - `scope_type batch`
  - `scope_value 1`
- Impacto:
  - o sistema continua aceitando comparação por lote mesmo após a regra operacional ter sido migrada para comparação mensal
  - isso permite gerar novas execuções fora do fluxo que a interface agora comunica ao usuário
- Por que isso é evidência:
  - o endpoint `/comparisons/run/{batch_id}` continua registrado e operacional
  - a execução produz `ComparisonRun.scope_type == "batch"` em ambiente isolado
- Arquivos afetados:
  - `app/routers/comparisons.py`
  - `app/services/comparison_service.py`
- Reprodução: bem-sucedida
- Confiança: alta

## BUG-005

- Tipo: `bug_reproduzivel`
- Método:
  - reprodução em banco temporário após executar uma comparação por lote via endpoint ainda exposto
  - leitura de `app/services/dashboard_service.py` e `app/routers/history.py`
- Saída observada:
  - `dashboard_latest_run_is_none True`
  - `history_shows_no_comparisons True`
- Impacto:
  - quando uma comparação por lote é criada, o dashboard e o histórico mensal passam a ocultar esse resultado
  - o sistema permite gerar uma execução que depois fica invisível nas visões principais, criando inconsistência operacional e de auditoria
- Por que isso é evidência:
  - o dashboard busca apenas `scope_type == "competencia"`
  - o histórico de comparações também filtra apenas `scope_type == "competencia"`
  - a reprodução isolada confirmou que um batch run existente não aparece em nenhuma das duas visões
- Arquivos afetados:
  - `app/services/dashboard_service.py`
  - `app/routers/history.py`
  - `app/routers/comparisons.py`
- Reprodução: bem-sucedida
- Confiança: alta
