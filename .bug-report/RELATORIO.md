# RELATORIO

## Executive summary

Foi corrigido o `BUG-007`, que fazia a página de histórico continuar exibindo lotes excluídos logicamente. A correção foi mínima: o histórico agora ignora `ImportBatch` com `deleted_at` preenchido, e um teste de regressão foi adicionado para garantir o fluxo. O `RISK-001` permanece pendente por envolver endurecimento de configuração de deploy.

## Findings by category

- `bug_reproduzivel`
  - `BUG-007`: lotes com `deleted_at` definido continuam visíveis em `/history`.
- `risco_potencial`
  - `RISK-001`: `APP_SECRET_KEY` opcional com fallback previsível (`apr-conciliador-dev-key`).

## Fixes applied

- Corrigido o `BUG-007` em `app/routers/history.py` com filtro por `deleted_at IS NULL`.
- Adicionado teste de regressão em `tests/test_routes.py`.
- Registrada a correção em `.bug-report/correcoes/BUG-007.md`.

## Pending items and why they were not fixed

- `RISK-001`
  - não foi corrigido porque mexe em bootstrap/configuração de deploy
  - endurecer essa regra sem alinhar ambiente e documentação pode quebrar instalações locais existentes

## Validation performed

- `.venv/bin/pytest -q tests/test_routes.py`
  - resultado: `15 passed in 18.24s`
- reprodução do fluxo coberta por teste de regressão
  - resultado esperado validado: lote excluído logicamente não aparece mais em `/history`
- leitura efetiva de `settings.secret_key`
  - resultado: fallback previsível confirmado

## Known limitations of the analysis

- A verificação de segurança foi estática e local; não houve ambiente remoto exposto para validar exploração real.
- Não há testes E2E de navegador cobrindo o histórico após exclusão lógica.
- A análise se concentrou nas áreas de maior risco funcional e de configuração; não foi feita revisão linha a linha de todo o repositório.

## Practical recommendations

- Exigir `APP_SECRET_KEY` fora de modo explicitamente local/desenvolvimento.

## Residual risks

- Se a aplicação for exposta com a chave padrão, a integridade da sessão web depende de um segredo publicamente previsível.
