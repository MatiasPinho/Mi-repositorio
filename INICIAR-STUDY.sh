#!/usr/bin/env bash
set -u

cd "$(dirname "${BASH_SOURCE[0]}")"

VENV_PYTHON="$PWD/.venv/bin/python"

if [[ ! -x "$VENV_PYTHON" ]]; then
  echo
  echo "ERROR: el entorno aislado de Carpeta esta incompleto."
  echo "Ejecuta: bash INSTALAR-STUDY.sh"
  exit 1
fi

# Fallar temprano en vez de descubrir dependencias o Chromium faltantes durante un run largo.
if ! "$VENV_PYTHON" scripts/setup_env.py check >/dev/null 2>&1; then
  echo
  echo "ERROR: el entorno aislado de Carpeta esta incompleto."
  echo "Ejecuta: bash INSTALAR-STUDY.sh"
  echo
  "$VENV_PYTHON" scripts/setup_env.py check
  exit 1
fi

"$VENV_PYTHON" study.py
status=$?

if [[ $status -ne 0 ]]; then
  echo
  echo "Carpeta termino con un error."
  echo "Revisa el mensaje anterior."
fi

exit "$status"
