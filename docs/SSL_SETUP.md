# TLS Setup and Certificate Rotation

This guide explains how to enable TLS for Redpanda and the FastAPI service and how to rotate certificates.

## Generating Certificates

Run `docker/generate-certs.sh` to create a small certificate authority and issue certificates for Redpanda and clients:

```bash
bash docker/generate-certs.sh
```

Certificates will be placed under `docker/certs/`:

- `ca.crt` – Certificate authority
- `redpanda.crt`/`redpanda.key` – Server certificate used by Redpanda
- `client.crt`/`client.key` – Client certificate used by the API and demo scripts

## Configuring Redpanda

The `docker/docker-compose.yml` file mounts these certificates and starts Redpanda with TLS enabled on port `29093`.
Clients should connect using the CA and client certificates via the environment variables `KAFKA_CA_CERT`, `KAFKA_CLIENT_CERT` and `KAFKA_CLIENT_KEY`.

## Running FastAPI with TLS

Start the API using Uvicorn and point it to the generated certificates:

```bash
uvicorn ume.api:app \
    --host 0.0.0.0 --port 8443 \
    --ssl-keyfile docker/certs/client.key \
    --ssl-certfile docker/certs/client.crt \
    --ssl-ca-certs docker/certs/ca.crt
```

## Certificate Rotation

To rotate certificates:

1. Run `docker/generate-certs.sh` again. It will create new certificates while keeping the CA unless removed.
2. Restart Redpanda and any clients so they pick up the new certificates.
3. Update any long‑running FastAPI processes by restarting Uvicorn with the new files.

Keeping the CA stable allows clients to trust new server certificates without further configuration. If the CA itself is rotated, distribute the new `ca.crt` to all clients and restart them.
