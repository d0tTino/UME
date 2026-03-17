#!/usr/bin/env bash
set -euo pipefail

tracked_disallowed=$(git ls-files 'docker/secrets/*' \
  | rg -v '^docker/secrets/README\.md$|^docker/secrets/[^/]+\.example$' || true)

if [ -n "$tracked_disallowed" ]; then
  echo "Disallowed tracked files detected in docker/secrets/:"
  echo "$tracked_disallowed"
  echo "Only README.md and *.example files may be committed."
  exit 1
fi

echo "docker/secrets guard passed"
