# Docker secrets

This directory is intentionally committed with **templates only**.

## Version-controlled files

- `README.md`
- `*.example` secret templates

## Local secret bootstrap

Create runtime secret files (`*.txt`) from environment variables before running Docker Compose:

```bash
./scripts/bootstrap_docker_secrets.sh
```

By default, the script writes:

- `docker/secrets/neo4j_password.txt`
- `docker/secrets/kafka_sasl_password.txt`
- `docker/secrets/ume_api_token.txt`
- `docker/secrets/ume_oauth_password.txt`

You can override values with environment variables:

- `NEO4J_PASSWORD`
- `KAFKA_SASL_PASSWORD`
- `UME_API_TOKEN`
- `UME_OAUTH_PASSWORD`

> Never commit generated `docker/secrets/*.txt` files.
