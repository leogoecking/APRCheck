# AGENTS.md

## Projeto
Sistema local de conciliação de APRs para rodar em servidor com VM Debian.

## Objetivo principal
Criar e manter um sistema web local que permita:

1. cadastrar APRs manualmente ao longo do mês
2. importar APRs vindas de arquivos CSV ou XML exportados do sistema principal
3. comparar os registros manuais com os importados
4. identificar divergências
5. exibir dashboard com indicadores
6. registrar histórico de importações e comparações
7. impedir duplicidade de IDs

---

## Regra de negócio mais importante
A comparação deve ser feita **sempre e exclusivamente pelo ID da APR**.

### Regras obrigatórias
- O campo `apr_id` é a única chave de comparação.
- Outros campos podem existir apenas para exibição, auditoria, contexto e relatórios.
- Nenhum outro campo pode alterar o resultado da comparação.
- Não permitir duplicidade de `apr_id` no cadastro manual.
- Detectar duplicidade de `apr_id` dentro de arquivos importados.
- Duplicidades no importado devem ser tratadas como alerta ou erro.
- O sistema deve persistir histórico de importações e execuções de comparação.

---

## Stack padrão do projeto
Use esta stack por padrão, salvo justificativa técnica muito forte:

- **Backend:** Python 3.12+
- **Framework backend:** FastAPI
- **Templates frontend:** Jinja2
- **Estilo:** CSS simples ou Bootstrap leve
- **Banco de dados:** SQLite
- **ORM / acesso a dados:** SQLAlchemy
- **Servidor local:** Uvicorn
- **Deploy Debian:** systemd

### Motivo da escolha
Essa stack é simples, robusta, leve, fácil de manter e adequada para ambiente local em Debian, sem complexidade desnecessária.

---

## Escopo funcional obrigatório

### 1. Dashboard
O sistema deve ter uma tela inicial com indicadores como:
- total de APRs manuais
- total de APRs importadas
- total de IDs conciliados
- total faltando no manual
- total faltando no importado
- total de duplicidades
- quantidade de importações realizadas
- resumo da última comparação

### 2. Cadastro manual de APR
Deve existir:
- formulário de cadastro manual
- listagem de APRs manuais
- busca por ID
- edição básica
- exclusão opcional, se implementada de forma segura

Campos mínimos:
- `apr_id` obrigatório e único
- `data_referencia`
- `responsavel`
- `descricao`
- `observacao`
- `status`

### 3. Importação de arquivos
Deve permitir:
- upload de CSV
- upload de XML
- leitura tolerante a colunas extras
- validação do ID
- detecção de registros inválidos
- detecção de duplicidade dentro do arquivo
- registro de lote de importação

### 4. Comparação / conciliação
Deve gerar pelo menos:
- conciliados
- faltando no manual
- faltando no importado
- duplicados
- inválidos

A comparação sempre deve ocorrer por lote, período ou competência.

### 5. Divergências
Deve existir tela para:
- visualizar divergências
- filtrar por categoria
- buscar por ID
- visualizar detalhe do problema
- exportar CSV, se possível no MVP

### 6. Histórico
Registrar:
- importações realizadas
- execuções de comparação
- data/hora
- quantidade de registros
- resumo consolidado

---

## Requisitos de modelagem de banco

A base deve incluir, no mínimo, estas tabelas ou equivalentes:

### `manual_aprs`
Campos mínimos:
- `id`
- `apr_id` UNIQUE NOT NULL
- `data_referencia`
- `responsavel`
- `descricao`
- `observacao`
- `status`
- `created_at`
- `updated_at`

### `import_batches`
Campos mínimos:
- `id`
- `nome_arquivo`
- `tipo_arquivo`
- `competencia`
- `total_registros`
- `total_validos`
- `total_invalidos`
- `total_duplicados`
- `created_at`

### `imported_aprs`
Campos mínimos:
- `id`
- `batch_id`
- `apr_id`
- `payload_json` ou campos equivalentes
- `is_valid`
- `error_message`
- `created_at`

### `comparison_runs`
Campos mínimos:
- `id`
- `batch_id`
- `competencia`
- `total_manual`
- `total_importado`
- `total_conciliado`
- `total_faltando_manual`
- `total_faltando_importado`
- `total_duplicados`
- `created_at`

### `comparison_items`
Campos mínimos:
- `id`
- `comparison_run_id`
- `apr_id`
- `origem`
- `status_comparacao`
- `detalhe`
- `created_at`

### Restrições obrigatórias
- `manual_aprs.apr_id` deve ser único
- criar índices para `apr_id`
- manter relacionamento coerente entre lote, importação e comparação
- impedir inconsistências básicas via constraints e validações de aplicação

---

## Regras de implementação

### Sempre faça
- gerar código real e funcional
- manter o projeto simples e organizado
- validar entradas
- tratar erros básicos
- garantir consistência entre rotas, models, services e templates
- documentar como rodar localmente
- incluir `requirements.txt`
- incluir `README.md`
- incluir exemplo de service `systemd`
- incluir inicialização de banco
- incluir estrutura pronta para evolução futura

### Nunca faça
- não comparar por nome, data, descrição ou outros campos
- não usar microserviços
- não usar dependências pesadas sem necessidade
- não deixar persistência em memória
- não gerar pseudocódigo no lugar de implementação
- não criar abstrações exageradas
- não ignorar duplicidade
- não deixar a lógica central ambígua

---

## Estrutura esperada do projeto

A estrutura deve seguir algo próximo disso:

```text
apr-conciliador/
├─ app/
│  ├─ main.py
│  ├─ config.py
│  ├─ db.py
│  ├─ models/
│  ├─ schemas/
│  ├─ routers/
│  ├─ services/
│  ├─ templates/
│  ├─ static/
│  └─ utils/
├─ data/
│  └─ app.db
├─ scripts/
│  └─ init_db.py
├─ docs/
├─ requirements.txt
├─ README.md
├─ AGENTS.md
└─ apr-conciliador.service

Pode adaptar levemente, mas sem perder clareza.

Organização recomendada de responsabilidades
routers/

Responsável por:

rotas web

recebimento de formulários

upload de arquivos

renderização de templates

endpoints auxiliares

services/

Responsável por:

parsing de CSV

parsing de XML

validação de IDs

detecção de duplicados

execução da conciliação

geração de resumos

models/

Responsável por:

entidades do banco

constraints

relacionamentos

templates/

Responsável por:

dashboard

cadastro manual

listagem manual

importação

divergências

histórico

Regras da importação
CSV

aceitar cabeçalhos variados, desde que o ID possa ser identificado ou mapeado

tolerar colunas extras

marcar registros sem ID como inválidos

detectar duplicidades dentro do mesmo arquivo

XML

fazer parser robusto

identificar nós de registro de APR

extrair o ID

tolerar campos extras

marcar registros sem ID como inválidos

detectar duplicidades

ID

obrigatório

remover espaços extras nas bordas

padronizar leitura com segurança

tratar vazio como inválido

registrar motivo do erro

Regras da comparação

A conciliação deve ser implementada com base em conjuntos de IDs.

Conjuntos mínimos

IDs manuais válidos

IDs importados válidos

IDs importados duplicados

IDs inválidos importados

Resultado esperado

conciliados = interseção entre manual e importado

faltando_no_manual = IDs presentes no importado e ausentes no manual

faltando_no_importado = IDs presentes no manual e ausentes no importado

duplicados = IDs repetidos no importado e qualquer outra duplicidade detectada

invalidos = registros sem ID ou com erro de leitura

Regra crítica

Nenhum campo além de apr_id participa da lógica de conciliação.

Interface esperada
Telas obrigatórias

Dashboard

Cadastro manual de APR

Listagem manual

Importação de arquivo

Resultado de comparação

Divergências

Histórico

UX desejada

interface limpa

navegação simples

feedback visual claro

mensagens de sucesso e erro

destaque para divergências

filtros básicos por categoria, competência e ID

Segurança e integridade

Como é um sistema local interno, use segurança proporcional, sem exagero, mas com boas práticas:

validar inputs no backend

sanitizar dados renderizados

tratar upload com cuidado

limitar extensões aceitas

registrar erros relevantes

evitar SQL inseguro

não confiar em dados do arquivo importado

garantir unicidade de apr_id no manual com constraint real no banco

Se autenticação for adicionada depois, preparar de forma evolutiva, mas o MVP pode ser sem login se isso simplificar o projeto.

Critérios de pronto

Considere a tarefa pronta somente se:

o sistema roda localmente no Debian

o banco SQLite está funcional

o cadastro manual está funcional

a importação CSV/XML está funcional

a comparação por ID está funcional

o dashboard está funcional

a tela de divergências está funcional

existe proteção contra duplicidade

existe histórico básico de importações e comparações

o projeto tem instruções de instalação e execução

Forma de resposta esperada ao gerar o projeto

Sempre entregar nesta ordem:

arquitetura escolhida e justificativa curta

estrutura de pastas

código de cada arquivo principal com caminho do arquivo

instruções para instalar no Debian

instruções para rodar localmente

exemplo de serviço systemd

melhorias futuras

Convenções de código

usar nomes claros e consistentes

evitar funções gigantes

separar parsing, comparação e persistência

manter baixa complexidade

comentar apenas quando agregar valor

preferir código explícito ao “mágico”

garantir imports corretos

manter consistência entre nomes de tabelas, campos e rotas

Instruções finais para o agente

Ao trabalhar neste projeto:

preserve a regra central de comparação por ID

priorize simplicidade, robustez e manutenção

não mude a stack sem necessidade real

não crie complexidade desnecessária

entregue sempre algo executável

revise se há risco de duplicidade não tratada

revise se algum trecho está comparando por algo além do ID

revise se o sistema está coerente com ambiente local Debian

Se houver dúvida entre duas abordagens, escolha a mais simples, mais estável e mais fácil de manter.