#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$ROOT_DIR/.venv"
PYTHON_BIN="${PYTHON_BIN:-python3}"

is_server_environment() {
    [ -n "${PORT:-}" ] ||
    [ -n "${APP_PORT:-}" ] ||
    [ -n "${K_SERVICE:-}" ] ||
    [ -n "${DYNO:-}" ] ||
    [ -n "${RENDER:-}" ] ||
    [ -n "${RAILWAY_ENVIRONMENT:-}" ] ||
    [ -n "${KUBERNETES_SERVICE_HOST:-}" ] ||
    [ -f "/.dockerenv" ]
}

detect_host() {
    if [ -n "${HOST:-}" ]; then
        printf '%s\n' "$HOST"
        return
    fi

    if [ -n "${APP_HOST:-}" ]; then
        printf '%s\n' "$APP_HOST"
        return
    fi

    printf '%s\n' "0.0.0.0"
}

detect_port() {
    if [ -n "${PORT:-}" ]; then
        printf '%s\n' "$PORT"
        return
    fi

    if [ -n "${APP_PORT:-}" ]; then
        printf '%s\n' "$APP_PORT"
        return
    fi

    printf '%s\n' "8000"
}

probe_port() {
    local host="$1"
    local port="$2"

    "$PYTHON_BIN" - "$host" "$port" <<'PY'
import errno
import socket
import sys

host = sys.argv[1]
port = int(sys.argv[2])

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

try:
    sock.bind((host, port))
except OSError as exc:
    if exc.errno in {errno.EADDRINUSE, getattr(errno, "WSAEADDRINUSE", 10048)}:
        sys.exit(1)
    if exc.errno in {errno.EACCES, errno.EPERM}:
        sys.exit(2)
    sys.exit(3)
finally:
    try:
        sock.close()
    except OSError:
        pass
PY
}

find_available_port() {
    local host="$1"
    local start_port="$2"
    local port="$start_port"

    while true; do
        if probe_port "$host" "$port"; then
            printf '%s\n' "$port"
            return
        fi

        case $? in
            1)
                port=$((port + 1))
                if [ "$port" -gt 65535 ]; then
                    echo "Erro: não foi encontrada porta livre a partir de $start_port." >&2
                    exit 1
                fi
                ;;
            2)
                echo "Erro: o ambiente atual não permite abrir sockets em $host:$port." >&2
                exit 1
                ;;
            *)
                echo "Erro: falha ao testar a porta $port em $host." >&2
                exit 1
                ;;
        esac
    done
}

detect_reload() {
    if [ -n "${RELOAD:-}" ]; then
        printf '%s\n' "$RELOAD"
        return
    fi

    if [ -n "${CI:-}" ] || is_server_environment; then
        printf '%s\n' "false"
    else
        printf '%s\n' "true"
    fi
}

HOST="$(detect_host)"
PORT="$(detect_port)"
RELOAD="$(detect_reload)"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    echo "Erro: python3 não encontrado." >&2
    exit 1
fi

if [ ! -d "$VENV_DIR" ]; then
    echo "Criando ambiente virtual em $VENV_DIR..."
    "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

VENV_PYTHON="$VENV_DIR/bin/python"
VENV_PIP="$VENV_DIR/bin/pip"

echo "Instalando dependências..."
"$VENV_PIP" install -r "$ROOT_DIR/requirements.txt"

echo "Inicializando banco..."
"$VENV_PYTHON" "$ROOT_DIR/scripts/init_db.py"

REQUESTED_PORT="$PORT"
PORT="$(find_available_port "$HOST" "$PORT")"

UVICORN_ARGS=(app.main:app --host "$HOST" --port "$PORT")
if [ "$RELOAD" = "true" ]; then
    UVICORN_ARGS+=(--reload)
fi

if [ "$PORT" != "$REQUESTED_PORT" ]; then
    echo "Porta $REQUESTED_PORT ocupada. Usando porta livre $PORT."
fi

echo "Subindo aplicação em http://$HOST:$PORT"
echo "Modo reload: $RELOAD"
exec "$VENV_DIR/bin/uvicorn" "${UVICORN_ARGS[@]}"
