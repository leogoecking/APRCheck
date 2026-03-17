# 01 - Reconhecimento

## Stack detectada

- Linguagem principal: Python 3.11.2 no `.venv`
- Framework web: FastAPI
- Templates: Jinja2
- ORM/acesso a dados: SQLAlchemy 2.x
- Banco: SQLite
- Servidor local: Uvicorn
- Test runner: pytest 8.4.2
- Dependências adicionais observadas: `python-multipart`, `httpx`, `openpyxl`

## Comandos relevantes descobertos

- Instalar dependências: `pip install -r requirements.txt`
- Inicializar banco: `python scripts/init_db.py`
- Subir aplicação: `./run.sh`
- Testes: `.venv/bin/pytest`

## Ferramentas verificadas no ambiente

- `python3`: disponível
- `.venv/bin/python`: disponível
- `.venv/bin/pip`: disponível
- `sqlite3`: disponível
- `pytest`: disponível via `.venv/bin/pytest`
- `git`: disponível
- `rg`: indisponível no ambiente atual

## Estrutura principal e entrypoints

- Entrypoint da aplicação: `app/main.py`
- Configuração: `app/config.py`
- Banco e sessão: `app/db.py`
- Modelos: `app/models/entities.py`
- Rotas web: `app/routers/*.py`
- Lógica de importação: `app/services/import_service.py`
- Lógica de conciliação: `app/services/comparison_service.py`
- Lógica manual/auditoria: `app/services/manual_apr_service.py`, `app/services/manual_audit_service.py`
- Templates: `app/templates/`
- Script operacional local: `run.sh`
- Unidade de serviço: `apr-conciliador.service`
- Testes: `tests/test_import_and_comparison.py`, `tests/test_routes.py`

## Comportamento funcional observado

- A conciliação usa conjuntos de `apr_id` e ignora outros campos na regra principal.
- O cadastro manual tem `apr_id` único em banco.
- Importação CSV/XML detecta `apr_id` ausente e duplicidade no lote.
- Há histórico persistido para importações, comparações e auditoria manual.
- Há exclusão de APR manual e exclusão de lote importado.

## Mapa inicial de risco

- Upload e parsing de arquivo: `app/services/import_service.py`
- Escritas em banco e integridade de histórico: `app/services/import_service.py`, `app/models/entities.py`
- Regra central de conciliação por competência/ID: `app/services/comparison_service.py`
- UX de formulários e redirects: `app/routers/*.py`, `app/utils/web.py`, `app/templates/base.html`
- Deploy/startup local: `run.sh`, `apr-conciliador.service`

## Limitações encontradas

- `rg` não está instalado, então a inspeção textual foi feita com `find`, `sed` e `nl`.
- O ambiente virtual atual estava inconsistente com o código: `itsdangerous` não estava instalado, apesar de a aplicação depender de `SessionMiddleware`.
- Não há suíte end-to-end/browser; os testes cobrem bem serviços e rotas, mas não validam fluxos reais de sessão/flash no navegador.
- O repositório já contém `data/app.db`, então reproduções isoladas foram feitas com bancos temporários em `/tmp` para evitar interferência.
