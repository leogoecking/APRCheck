# Conciliador de APR

Sistema web local para cadastro manual, importação CSV/XML e conciliação de APRs exclusivamente por `apr_id`.

## Arquitetura escolhida

Monólito simples em `FastAPI + Jinja2 + SQLAlchemy + SQLite`, com rotas web, serviços de domínio separados e persistência local. A escolha prioriza simplicidade operacional em Debian, facilidade de manutenção e regra de conciliação isolada por ID.

## Estrutura de pastas

```text
APRCheck/
├─ app/
│  ├─ main.py
│  ├─ config.py
│  ├─ db.py
│  ├─ models/
│  ├─ routers/
│  ├─ schemas/
│  ├─ services/
│  ├─ static/
│  ├─ templates/
│  └─ utils/
├─ data/
├─ docs/
├─ scripts/
├─ tests/
├─ requirements.txt
├─ README.md
├─ apr-conciliador.service
└─ AGENTS.md
```

## Funcionalidades do MVP

- Dashboard com totais e resumo da última comparação.
- Cadastro manual com criação, listagem, busca por ID e edição.
- Importação de CSV/XML com competência manual por lote.
- Validação de IDs, tolerância a colunas extras e detecção de duplicados no lote.
- Conciliação manual por lote baseada somente em `apr_id`.
- Tela de divergências com filtros e exportação CSV.
- Histórico de importações e comparações.

## Instalação no Debian

1. Instale Python 3.12+, `venv` e SQLite:

```bash
sudo apt update
sudo apt install -y python3 python3-venv sqlite3
```

2. Copie o projeto para o servidor, por exemplo em `/opt/apr-conciliador`.

3. Crie e ative um ambiente virtual:

```bash
cd /opt/apr-conciliador
python3 -m venv .venv
source .venv/bin/activate
```

4. Instale as dependências:

```bash
pip install -r requirements.txt
```

5. Inicialize o banco:

```bash
python scripts/init_db.py
```

## Execução local

```bash
uvicorn app.main:app --reload
```

Abra `http://127.0.0.1:8000`.

## Execução via systemd

1. Ajuste os caminhos em `apr-conciliador.service` se necessário.
2. Copie o arquivo:

```bash
sudo cp apr-conciliador.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now apr-conciliador
```

3. Verifique status:

```bash
sudo systemctl status apr-conciliador
```

## Rodando os testes

```bash
pytest
```

## Melhorias futuras

- Ajustar o parser para layouts reais de XML/CSV do sistema principal.
- Adicionar paginação nas listagens.
- Incluir autenticação simples se o ambiente exigir.
- Permitir exportações adicionais por lote e comparação.
