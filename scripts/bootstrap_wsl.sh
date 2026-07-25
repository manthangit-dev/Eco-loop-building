#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${PROJECT_ROOT}"

python3 --version
python3 -c 'import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 12) else "Python 3.12 is required.")'

if [[ ! -d ".venv" ]]; then
  python3 -m venv .venv
fi

PYTHON="${PROJECT_ROOT}/.venv/bin/python"
"${PYTHON}" -m pip install --upgrade pip setuptools wheel
"${PYTHON}" -m pip install -r requirements-dev.txt

if [[ ! -f ".env" ]]; then
  cp ".env.example" ".env"
  echo "Created .env from .env.example; review ENERGYPLUS_HOME."
fi

echo "Activate later with: source .venv/bin/activate"
"${PYTHON}" scripts/check_environment.py
