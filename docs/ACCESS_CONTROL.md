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

#### Running the API with analytics permissions

```bash
UME_API_ROLE=AnalyticsAgent uvicorn ume.api:app
```

Requests to `/analytics/*` will succeed. If the role is anything else, the API
responds with HTTP 403.

#### Editing a user profile via the CLI

```bash
UME_ROLE=UserService ume new_node UserProfile.123 '{}'
```

Without the `UserService` role the command raises `AccessDeniedError`.

## Permission Graph Model

Permissions are stored within the graph using dedicated node and edge types
introduced in schema version `3.0.0`.

- `User` nodes represent individual actors.
- `UserGroup` nodes collect users for shared access.
- Resources link to owners via `OWNED_BY` edges.
- `SHARED_WITH` edges grant group access and may include a `permission_level`
  property such as `viewer` or `editor`.

### Group Membership Checks

The service now verifies that callers belong to any groups referenced by
`SHARED_WITH` edges. Membership is taken from the group's `members` list and a
request from a non-member returns `HTTP 403` even if a share exists. This
prevents users from escalating privileges by guessing group identifiers.

### `PUBLIC_TO_GROUP` Visibility

Some resources include a `visibility` attribute. When a resource is owned by a
`UserGroup` and the `visibility` is set to `PUBLIC_TO_GROUP`, all members of that
group automatically gain viewer permissions. Editing still requires a
`SHARED_WITH` edge specifying `permission_level: editor`.

For example, a calendar event owned by `Group.eng` with
`PUBLIC_TO_GROUP` visibility allows every member to read it. If `User.u1` has an
additional `SHARED_WITH` edge granting `editor` access, they can update or delete
the event while other members remain read-only viewers.

### Sample Requests

Retrieve nodes owned by a user:

```bash
curl "http://localhost:8000/v1/nodes?user_id=User.u1"
```

Retrieve nodes shared with a group:

```bash
curl "http://localhost:8000/v1/nodes/shared?group_id=Group.g1"
```

Both endpoints require an authenticated role as described above.

## Dossier Endpoint RBAC

API routes under `/dossier` use their own role checks. Three roles are
implemented today:

- **ProjectManager** – allowed to view any dossier and attach new projects.
- **Viewer** – allowed to view dossier information but not modify it.
- **TelemetryAdmin** – allowed to create snapshots and update activity logs.

The HTTP server reads the current role from the
OAuth token via `UME_OAUTH_ROLE`. Command line tools can specify `UME_ROLE` to
emulate the same restrictions.

## User Consent Ledger

The privacy agent checks user consent before forwarding sanitized events.
Consent records are stored in a lightweight SQLite ledger located at
`UME_CONSENT_LEDGER_PATH` (default `consent_ledger.db`). Each entry records the
`user_id`, the consent `scope`, and the time consent was granted.

When processing events the privacy agent looks for `user_id` and `scope` fields
in the event payload. If no matching consent entry is found, the sanitized event
is published to the quarantine topic instead of the clean events topic.

Policy enforcement in the graph write path happens in
`processing.apply_event_to_graph()`, which runs each registered alignment plugin
before mutating graph state. Rego policies are provided through the
`RegoPolicyEngine` plugin in `src/ume/plugins/alignment`: it uses `OPAClient`
when `UME_OPA_URL` is set, and falls back to local `regopy` evaluation when OPA
is not configured.

`RegoPolicyEngine` evaluates the full event object as policy input
(`event.__dict__`), so policies can read envelope and payload fields (for
example `input.payload.consent`, `input.event_type`, or `input.node_id`) but
should not expect a serialized graph snapshot.

Consent can be granted or revoked programmatically using the
`ConsentLedger` class from `ume.consent_ledger`.

For policy pipeline extension, ordering, and stage registry configuration, see
[`docs/POLICY_PIPELINE.md`](./POLICY_PIPELINE.md).

### Ledger Encryption Migration

UME can optionally encrypt the audit log and SQLite ledgers. Enable this by
setting `UME_ENCRYPTION_ENABLED` to `True` and providing a base64 encoded key
via `UME_ENCRYPTION_KEY`. When enabled, both the event and consent ledgers will
be written in encrypted form alongside the audit log. Existing plaintext files
must be re-encrypted or replaced. The simplest migration is to archive the old
files and let UME create new, encrypted ones on startup.

## Sample Rego Rules

The following snippet demonstrates how dossier permissions could be expressed
in Rego.

```rego
package ume.dossier

# Allow reading projects if that section is shareable or the caller has a valid role
default can_read_projects = false

can_read_projects {
    input.metadata.shareable_projects
}

can_read_projects {
    input.role == "ProjectManager"
}

can_read_projects {
    input.role == "Viewer"
}

# Allow reading reflections if that section is shareable
# or the caller has a valid role
default can_read_reflections = false

can_read_reflections {
    input.metadata.shareable_reflections
}

can_read_reflections {
    input.role == "ProjectManager"
}

can_read_reflections {
    input.role == "Viewer"
}

# Allow reading skills if that section is shareable or the caller has a valid role
default can_read_skills = false

can_read_skills {
    input.metadata.shareable_skills
}

can_read_skills {
    input.role == "ProjectManager"
}

can_read_skills {
    input.role == "Viewer"
}

# Allow reading values if that section is shareable or the caller has a valid role
default can_read_values = false

can_read_values {
    input.metadata.shareable_values
}

can_read_values {
    input.role == "ProjectManager"
}

can_read_values {
    input.role == "Viewer"
}

# Allow reading memories if that section is shareable or the caller has a valid role
default can_read_memories = false

can_read_memories {
    input.metadata.shareable_memories
}

can_read_memories {
    input.role == "ProjectManager"
}

can_read_memories {
    input.role == "Viewer"
}

allow_add_project {
    input.role == "ProjectManager"
}

can_modify_telemetry {
    input.role == "TelemetryAdmin"
}
```
