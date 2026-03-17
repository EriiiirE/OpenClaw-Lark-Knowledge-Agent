#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY_SCRIPT="${SCRIPT_DIR}/pkai_rag_query.py"
DEFAULT_PKAI_ROOT="$(cd "${SCRIPT_DIR}/../../../../.." && pwd)"
PKAI_ROOT="${PKAI_ROOT:-${DEFAULT_PKAI_ROOT}}"

if [[ -n "${PKAI_PYTHON:-}" && -x "${PKAI_PYTHON}" ]]; then
  PYTHON_BIN="${PKAI_PYTHON}"
elif [[ -x "${PKAI_ROOT}/.venv-mac/bin/python" ]]; then
  PYTHON_BIN="${PKAI_ROOT}/.venv-mac/bin/python"
elif [[ -x "${PKAI_ROOT}/.venv/bin/python" ]]; then
  PYTHON_BIN="${PKAI_ROOT}/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python3)"
else
  printf '%s\n' '{"ok": false, "error": "No python interpreter found."}'
  exit 1
fi

export PKAI_ROOT
exec "${PYTHON_BIN}" "${PY_SCRIPT}" "$@"
