# Security Notes

This document summarizes how to secure on-disk data for UME deployments.

## Encryption Options

Set `UME_ENCRYPTION_ENABLED=true` and define a base64 Fernet key in `UME_ENCRYPTION_KEY` to encrypt the SQLite ledgers and the audit log. When enabled, new ledger and log files are written in encrypted form. Archive or migrate any existing plaintext files.

## Recommended Storage Locations

By default the audit log and ledgers are created in the current working directory. In production these files should reside on a persistent volume with restricted permissions, e.g. `/var/lib/ume/`. Keep the directories readable only by the service account.

Relevant settings:

- `UME_AUDIT_LOG_PATH` – path to the audit log
- `UME_EVENT_LEDGER_PATH` – path to the event ledger
- `UME_CONSENT_LEDGER_PATH` – path to the consent ledger

## Ledger and Audit Key Management

Audit entries are signed with `UME_AUDIT_SIGNING_KEY`. Generate a unique key for every deployment and rotate it periodically. Store both the signing key and the encryption key securely outside of version control, such as in an environment file managed by a secrets vault.
