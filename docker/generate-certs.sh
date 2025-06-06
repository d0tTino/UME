#!/bin/bash
# Simple script to generate self-signed certificates for Redpanda and FastAPI
# Certificates are placed in docker/certs/
set -euo pipefail

CERT_DIR="$(dirname "$0")/certs"
mkdir -p "$CERT_DIR"

# Certificate authority
if [ ! -f "$CERT_DIR/ca.key" ]; then
    openssl genrsa -out "$CERT_DIR/ca.key" 4096
    openssl req -x509 -new -nodes -key "$CERT_DIR/ca.key" \
        -subj "/CN=UME-CA" -days 3650 -out "$CERT_DIR/ca.crt"
fi

# Server certificate for Redpanda
if [ ! -f "$CERT_DIR/redpanda.key" ]; then
    openssl genrsa -out "$CERT_DIR/redpanda.key" 4096
    openssl req -new -key "$CERT_DIR/redpanda.key" \
        -subj "/CN=redpanda" -out "$CERT_DIR/redpanda.csr"
    openssl x509 -req -in "$CERT_DIR/redpanda.csr" -CA "$CERT_DIR/ca.crt" \
        -CAkey "$CERT_DIR/ca.key" -CAcreateserial -out "$CERT_DIR/redpanda.crt" -days 365
fi

# Client certificate for API/producer/consumer
if [ ! -f "$CERT_DIR/client.key" ]; then
    openssl genrsa -out "$CERT_DIR/client.key" 4096
    openssl req -new -key "$CERT_DIR/client.key" \
        -subj "/CN=ume-client" -out "$CERT_DIR/client.csr"
    openssl x509 -req -in "$CERT_DIR/client.csr" -CA "$CERT_DIR/ca.crt" \
        -CAkey "$CERT_DIR/ca.key" -CAcreateserial -out "$CERT_DIR/client.crt" -days 365
fi

echo "Certificates generated in $CERT_DIR"
