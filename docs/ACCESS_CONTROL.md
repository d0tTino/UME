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
