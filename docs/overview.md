# Visão Geral

O Conciliador de APR é um sistema web local para cadastrar APRs manualmente, importar arquivos CSV/XML, comparar registros exclusivamente por `apr_id` e registrar histórico de lotes e comparações.

## Fluxo principal

1. Cadastrar APRs manualmente em `/manual-aprs`.
2. Importar um lote em `/imports`, informando a competência.
3. Executar a conciliação manualmente para o lote importado.
4. Consultar divergências em `/divergences`.
5. Acompanhar histórico em `/history`.

## Regra central

Somente `apr_id` participa da lógica de conciliação. Campos como data, descrição e responsável servem apenas para contexto, auditoria e exibição.
