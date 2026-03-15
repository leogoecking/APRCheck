# Visão Geral

O Conciliador de APR é um sistema web local para cadastrar APRs manualmente, importar arquivos CSV/XML, comparar registros exclusivamente por `apr_id` e registrar histórico de lotes, comparações e auditoria da base manual.

## Fluxo principal

1. Cadastrar APRs manualmente em `/manual-aprs`, individualmente, por texto colado ou por CSV da base manual.
2. Importar um lote em `/imports`, informando a competência.
3. Executar a conciliação manualmente por lote ou por competência.
4. Consultar divergências em `/divergences`.
5. Acompanhar histórico e auditoria em `/history`.

## Regra central

Somente `apr_id` participa da lógica de conciliação. Campos como data, assunto, descrição e responsável servem apenas para contexto, auditoria e exibição.
