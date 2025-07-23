#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

missing=0

check_poetry() {
    if [ "${UME_SKIP_POETRY_CHECK:-0}" = "1" ]; then
        return
    fi
    if ! command -v poetry >/dev/null 2>&1; then
        echo "Poetry not found. Attempting installation..."
        if command -v curl >/dev/null 2>&1; then
            curl -sSL https://install.python-poetry.org | python3 - && \
                export PATH="$HOME/.local/bin:$HOME/.poetry/bin:$PATH"
        else
            echo "Unable to install Poetry automatically."
            echo "Visit https://python-poetry.org/docs/#installation for manual instructions."
            missing=1
        fi
    fi
}

check_node() {
    if [ "${UME_SKIP_NODE_CHECK:-0}" = "1" ]; then
        return
    fi
    if ! command -v node >/dev/null 2>&1; then
        echo "Node.js not found. Install Node 18+ from https://nodejs.org/."
        missing=1
    fi
}

check_docker() {
    if [ "${UME_SKIP_DOCKER_CHECK:-0}" = "1" ]; then
        return
    fi
    if ! command -v docker >/dev/null 2>&1; then
        echo "Docker not found. Install Docker from https://docs.docker.com/get-docker/."
        missing=1
    fi
}

check_poetry
check_node
check_docker

if [ "$missing" -ne 0 ]; then
    echo "Missing required tools. Aborting."
    exit 1
fi

poetry install --with dev
poetry run ume up "$@"
