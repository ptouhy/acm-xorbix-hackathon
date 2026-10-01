#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "==> ACM x Xorbix Hackathon — environment setup"

# Colons in the project path break Python venv (PATH separator on macOS).
VENV_DIR=".venv"
if [[ "$ROOT" == *:* ]]; then
  VENV_DIR="${HOME}/.venvs/acm-xorbix-hackathon"
  echo "Project path contains ':' — using venv at $VENV_DIR"
fi

if [[ ! -d "$VENV_DIR" ]]; then
  echo "Creating virtual environment..."
  mkdir -p "$(dirname "$VENV_DIR")"
  python3 -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -e ".[dev,spark,databricks]"

if ! command -v databricks >/dev/null 2>&1; then
  echo "Installing Databricks CLI..."
  pip install databricks-cli
fi

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from template — add your workspace credentials after kickoff."
fi

echo ""
echo "Setup complete. Next steps:"
echo "  source \"$VENV_DIR/bin/activate\""
echo "  cp .env.example .env   # if not already done"
echo "  # Fill in DATABRICKS_HOST and DATABRICKS_TOKEN after kickoff"
echo "  pytest                 # verify install"
