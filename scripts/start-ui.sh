#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -x .venv/bin/streamlit ]]; then
  echo "Instale a interface primeiro: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
  exit 1
fi
exec .venv/bin/streamlit run app.py --server.address 127.0.0.1
