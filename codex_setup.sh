#!/usr/bin/env bash
set -euo pipefail

need_pkgs=()
command -v python3.12 >/dev/null 2>&1 || need_pkgs+=(python3.12 python3.12-venv python3.12-dev)
command -v gcc >/dev/null 2>&1 || need_pkgs+=(build-essential)
if [ "${#need_pkgs[@]}" -ne 0 ]; then
    sudo apt-get update
    sudo apt-get install -y "${need_pkgs[@]}"
fi

python3.12 -m pip install --upgrade pip poetry
if ! poetry install --with dev --no-interaction --no-ansi; then
    # If the lock file is out of sync, regenerate it and retry
    poetry lock
    poetry install --with dev --no-interaction --no-ansi
fi

# Download SpaCy model if desired
if poetry run python -m spacy validate en_core_web_lg >/dev/null 2>&1; then
    : # already installed
else
    poetry run python -m spacy download en_core_web_lg || true
fi

python3.12 -m pip install types-PyYAML types-pytz types-requests types-ujson
poetry run pre-commit install

echo "To check if tests and linters should run for your branch, execute:"
echo "python scripts/ci_should_run.py && echo 'Run tests' || echo 'Docs only, skipping'"
