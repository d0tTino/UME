#!/usr/bin/env bash
# Install all development and optional dependencies for local testing
set -euo pipefail

poetry install --with dev --all-extras "$@"
