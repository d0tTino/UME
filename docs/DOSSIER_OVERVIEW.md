# Dossier Overview

The user dossier is a lightweight collection of YAML files that track basic profile information and notes. UME loads the dossier from the directory specified by `UME_DOSSIER_PATH` (defaults to `~/.ume_dossier`). The directory is created automatically when missing.

## File Structure

A newly initialized dossier contains:

- `meta.yaml` – schema version metadata and shareable flags
- `profile.yaml` – basic user details (name, email)
- `projects.yaml` – list of active projects
- `preferences.yaml` – arbitrary key/value settings
- `reflections.yaml` – journal style reflections
- `knowledge.yaml` – saved knowledge or memories
- `values.yaml` – list of personal values
- `skills.yaml` – list of personal skills
- `telemetry/` – directory for captured traces

You can create the folder manually or call `Dossier.init_dossier(path)` from Python to copy the template files.

## Linking Entries

Projects and reflections are stored as objects that include a generated `id` field using `uuid4`.  Entries may reference other items by listing their IDs in a `links` array.  Helper functions automatically create the IDs and accept lists of related entry IDs when adding new records.

## Security Practices

Dossier API routes enforce role-based access. `ProjectManager` can add projects while `Viewer` may only read.
To secure audit logs, ledger files, and the dossier itself, enable encryption by setting `UME_ENCRYPTION_ENABLED=true` and defining a base64 key in `UME_ENCRYPTION_KEY`. When enabled, the YAML files and telemetry logs in `UME_DOSSIER_PATH` are stored encrypted on disk. Additional notes on key management can be found in [SECURITY_NOTES.md](SECURITY_NOTES.md).

## CLI Examples

```bash
# View a dossier using the running API
ume dossier view user123

# Attach a project to a dossier
ume dossier add-project user123 projectA

# Add a personal value
ume dossier add-value user123 honesty

# List values
ume dossier list-values user123

# Add a skill
ume dossier add-skill user123 python

# List skills
ume dossier list-skills user123

# List projects
ume dossier list-projects user123

# List reflections
ume dossier list-reflections user123

# Add a memory
ume dossier add-memory user123 "remember this"

# List memories
ume dossier list-memories user123
```

## API Examples

```bash
# Fetch dossier details
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/dossier/user123

# Add a project
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -d '{"dossier_id":"user123","project_id":"projectA"}' \
  http://localhost:8000/dossier/add-project

# Add a value
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -d '{"dossier_id":"user123","value":"honesty"}' \
  http://localhost:8000/dossier/add-value

# List values
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/dossier/values/user123
# Add a skill
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -d '{"dossier_id":"user123","skill":"python"}' \
  http://localhost:8000/dossier/add-skill

# List skills
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/dossier/skills/user123

# List projects
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/dossier/projects/user123

# List reflections
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/dossier/reflections/user123

# Add a memory
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -d '{"dossier_id":"user123","text":"remember this"}' \
  http://localhost:8000/dossier/add-memory

# List memories
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/dossier/memories/user123
```

## Listing Values

The `/dossier/values/{id}` route returns the list of personal values stored in a dossier.
Use `ume dossier list-values <id>` to fetch them via the CLI.

```bash
ume dossier list-values user123
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/dossier/values/user123
```

## Migrating Existing Dossiers

New releases may introduce additional dossier fields or change the
storage format. Update your local dossier after pulling updates by
running the migration helper:

```bash
poetry run python scripts/migrate_dossier.py ~/.ume_dossier
```

Pass `--encrypt` when enabling encryption so the files are re-written
with your `UME_ENCRYPTION_KEY`:

```bash
UME_ENCRYPTION_ENABLED=true UME_ENCRYPTION_KEY=<key> \
  poetry run python scripts/migrate_dossier.py --encrypt ~/.ume_dossier
```

## Dossier Snapshots

Use `Dossier.snapshot()` to archive the current YAML files. A folder named
`history/<timestamp>` is created inside the dossier directory containing
copies of all YAML files. Snapshots can also be created via the API or CLI:

```bash
curl -X POST -H "Authorization: Bearer <token>" \
  -d '{"dossier_id":"example"}' \
  http://localhost:8000/dossier/snapshot

ume dossier snapshot example
```

## Watcher Hooks

Importing `ume.watchers` automatically registers the `dossier_activity_hook`. When active, file events collected by watchers are appended to `telemetry/activity.log` inside the user's dossier.

### Enabling and Disabling Activity Logging

Activity logging is enabled by default. Set the environment variable
`UME_ACTIVITY_LOG_ENABLED=false` to prevent the watcher from registering
`dossier_activity_hook`. With the hook disabled, file events are ignored and no
entries are written to `telemetry/activity.log`. Using any value other than
`0`, `false`, or `no` re-enables the hook on the next import of
`ume.watchers`.

