#!/bin/bash
# Example ACL configuration for Redpanda using rpk.
# Run inside the docker compose environment where rpk is available.
set -e

# Create service accounts
rpk acl user create autodev || true
rpk acl user create culture_ai || true
rpk acl user create ume_service || true

# AutoDev permissions
rpk acl create --allow-principal User:autodev --operation produce --topic autodev-events
rpk acl create --allow-principal User:autodev --operation consume --topic autodev-events --group autodev-group

# Culture.ai permissions
rpk acl create --allow-principal User:culture_ai --operation produce --topic culture-events
rpk acl create --allow-principal User:culture_ai --operation consume --topic culture-events --group culture-group

# UME service permissions
rpk acl create --allow-principal User:ume_service --operation produce --topic ume-events
rpk acl create --allow-principal User:ume_service --operation consume --topic ume-events --group ume-group
