#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

BASE_PYTHON=""
for candidate in python3 python; do
  if command -v "$candidate" >/dev/null 2>&1; then
    if "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; then
      BASE_PYTHON="$candidate"
      break
    fi
  fi
done

if [[ -z "$BASE_PYTHON" ]]; then
  echo
  echo "ERROR: se necesita Python 3.10 o superior."
  echo "Instala Python 3 y vuelve a ejecutar: bash INSTALAR-STUDY.sh"
  exit 1
fi

VENV_PYTHON="$PWD/.venv/bin/python"

echo
echo "[1/6] Preparando entorno virtual aislado..."
if [[ ! -x "$VENV_PYTHON" ]]; then
  "$BASE_PYTHON" -m venv .venv
fi

if ! "$VENV_PYTHON" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; then
  echo
  echo "ERROR: .venv existe pero no contiene un Python valido."
  echo "Borra .venv y vuelve a ejecutar: bash INSTALAR-STUDY.sh"
  exit 1
fi

echo
echo "[2/6] Actualizando pip dentro de .venv..."
"$VENV_PYTHON" -m pip install --upgrade pip

echo
echo "[3/6] Instalando dependencias completas dentro de .venv..."
"$VENV_PYTHON" -m pip install -r requirements.txt

echo
echo "[4/6] Instalando Chromium para Playwright..."
"$VENV_PYTHON" -m playwright install chromium

echo
echo "[5/6] Verificando entorno aislado..."
"$VENV_PYTHON" -m pip check
"$VENV_PYTHON" scripts/setup_env.py check

echo
echo "[6/6] Configurando OpenCode y el MCP local..."
"$VENV_PYTHON" scripts/configure_opencode.py

echo
echo "=============================================="
echo "Carpeta esta lista para usar en Linux."
echo "Dependencias aisladas en .venv."
echo "OpenCode quedo configurado para university-study."
echo "Para iniciar Carpeta: bash INICIAR-STUDY.sh"
echo "=============================================="
