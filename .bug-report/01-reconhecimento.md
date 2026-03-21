# 01 - Reconhecimento

## Stack detectada

- Linguagem principal: Python 3.11.2
- Framework web: FastAPI
- Templates: Jinja2
- ORM/acesso a dados: SQLAlchemy 2.x
- Banco: SQLite
- Servidor local: Uvicorn
- Test runner: pytest 8.4.2
- Dependências relevantes observadas: `itsdangerous`, `python-multipart`, `httpx`, `openpyxl`

## Comandos relevantes descobertos

- Instalação de dependências: `pip install -r requirements.txt`
- Inicialização do banco: `python scripts/init_db.py`
- Subida local: `./run.sh`
- Testes: `.venv/bin/pytest`

## Ferramentas verificadas no ambiente

- `python3`: disponível
- `.venv/bin/python`: disponível
- `.venv/bin/pip`: disponível
- `.venv/bin/pytest`: disponível
- `git`: disponível
- `find`: disponível
- `sed`: disponível
- `sqlite3`: não verificado nesta rodada
- `rg`: indisponível no ambiente atual

## Estrutura principal e entrypoints

- Entrypoint principal: `app/main.py`
- Configuração: `app/config.py`
- Banco/sessão/migração compatível: `app/db.py`
- Modelos: `app/models/entities.py`
- Rotas HTTP: `app/routers/*.py`
- Serviços críticos:
  - importação: `app/services/import_service.py`
  - conciliação: `app/services/comparison_service.py`
  - cadastro manual/auditoria: `app/services/manual_apr_service.py`, `app/services/manual_audit_service.py`
- Templates: `app/templates/`
- Script operacional: `run.sh`
- Testes: `tests/test_import_and_comparison.py`, `tests/test_routes.py`

## Comandos e evidências executados

- `python3 --version`
- `.venv/bin/python --version`
- `.venv/bin/pytest --version`
- `.venv/bin/pytest -q`
- inspeção com `sed` dos arquivos centrais de configuração, rotas, serviços, modelos e templates
- reprodução isolada em banco temporário sob `/tmp/aprcheck-analysis-history`

## Mapa inicial de risco

- Upload e parsing de arquivos: `app/services/import_service.py`
- Escritas e exclusão lógica em banco: `app/services/import_service.py`, `app/services/manual_apr_service.py`
- Reexecução automática de comparações mensais: `app/services/comparison_service.py`
- Histórico e rastreabilidade operacional: `app/routers/history.py`, `app/templates/history/index.html`
- Configuração sensível e sessão web: `app/config.py`, `app/main.py`, `app/utils/web.py`

## Limitações encontradas

- `rg` não está instalado; a inspeção textual foi feita com `find`, `sed` e `nl`.
- Não há suíte E2E/browser; a validação de UI foi feita por inspeção de template e chamadas diretas de rotas.
- A análise de segurança ficou restrita ao contexto local do repositório; não houve validação de exposição real em rede além do comportamento padrão documentado no `README.md`.
