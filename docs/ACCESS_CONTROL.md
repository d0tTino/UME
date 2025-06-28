# Access Control

This document describes how access control is applied across UME components.

## Redpanda ACLs

Each sub-agent operates with its own service principal. Example accounts:

- `autodev`
- `culture_ai`
- `ume_service`

Use `rpk` to create accounts and restrict topic access. The script
`docker/setup-redpanda-acls.sh` contains example commands. Each agent is
limited to producing and consuming only its designated topics.

## Graph Role Based Access

The graph adapter includes a role based wrapper. Two roles are currently
enforced:

- **UserService** – allowed to create or update nodes whose IDs begin with
  `UserProfile.`.
- **AnalyticsAgent** – allowed to run advanced queries such as
  `find_connected_nodes`.

Other roles attempting these operations will receive an `AccessDeniedError`.

### Configuring Roles

`RoleBasedGraphAdapter` reads the role from the environment. When running the
HTTP API the `UME_API_ROLE` variable applies, while the command line interface
uses `UME_ROLE`. If either variable is set, the underlying graph adapter is
wrapped automatically.

### Example Use Cases

*Running the API with analytics permissions*

```bash
UME_API_ROLE=AnalyticsAgent uvicorn ume.api:app
```

Requests to `/analytics/*` will succeed. If the role is anything else, the API
responds with HTTP 403.

*Editing a user profile via the CLI*

```bash
UME_ROLE=UserService ume-cli new_node UserProfile.123 '{}'
```

Without the `UserService` role the command raises `AccessDeniedError`.

## User Consent Ledger

The privacy agent checks user consent before forwarding sanitized events.
Consent records are stored in a lightweight SQLite ledger located at
`UME_CONSENT_LEDGER_PATH` (default `consent_ledger.db`). Each entry records the
`user_id`, the consent `scope`, and the time consent was granted.

When processing events the privacy agent looks for `user_id` and `scope` fields
in the event payload. If no matching consent entry is found, the sanitized event
is published to the quarantine topic instead of the clean events topic. Rego
policies can reference this status via the `input.consent` value.

Consent can be granted or revoked programmatically using the
`ConsentLedger` class from `ume.consent_ledger`.
