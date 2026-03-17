#!/usr/bin/env bash
set -euo pipefail

secrets_dir="docker/secrets"
mkdir -p "$secrets_dir"

write_secret() {
  local out_file="$1"
  local value="$2"
  if [ -z "$value" ]; then
    echo "Missing required secret value for $out_file" >&2
    exit 1
  fi
  printf '%s\n' "$value" > "$out_file"
}

write_secret "$secrets_dir/neo4j_password.txt" "${NEO4J_PASSWORD:-change-me-in-local-dev}"
write_secret "$secrets_dir/kafka_sasl_password.txt" "${KAFKA_SASL_PASSWORD:-change-me-in-local-dev}"
write_secret "$secrets_dir/ume_api_token.txt" "${UME_API_TOKEN:-change-me-in-local-dev}"
write_secret "$secrets_dir/ume_oauth_password.txt" "${UME_OAUTH_PASSWORD:-change-me-in-local-dev}"

echo "Docker secret files generated in $secrets_dir"
