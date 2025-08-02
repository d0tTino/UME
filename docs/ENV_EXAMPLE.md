# Example .env

The `.env` file allows you to override default settings defined in `src/ume/config.py`. Values in this file are loaded before reading your shell environment.

An `env.example` file with the following contents is included at the project root.

```bash
# Path where the CLI stores its SQLite database
UME_CLI_DB=./ume.db

# Directory for the YAML dossier (user profile)
# Defaults to ~/.ume_dossier when unset
UME_DOSSIER_PATH=~/.ume_dossier

# Location for audit log entries
UME_AUDIT_LOG_PATH=./audit.log

# Key used to sign audit entries. Must be changed from the default.
UME_AUDIT_SIGNING_KEY=<your-key>
# Enable encryption of audit and ledger files
UME_ENCRYPTION_ENABLED=False
# Base64 Fernet key used when encryption is enabled
UME_ENCRYPTION_KEY=

# Credentials used to obtain OAuth tokens
UME_OAUTH_USERNAME=ume
UME_OAUTH_PASSWORD=password
UME_OAUTH_ROLE=AnalyticsAgent
UME_OAUTH_TTL=3600

# Optional role for the CLI (leave unset for full permissions)
UME_ROLE=view-only

# Endpoint for the LLM Ferry listener
LLM_FERRY_API_URL=https://example.com/api

# API key used by LLM Ferry
LLM_FERRY_API_KEY=

# Number of hours of events to include in Angel Bridge summaries
ANGEL_BRIDGE_LOOKBACK_HOURS=24
# Kafka broker configuration for the projection engine
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
# Topic containing sanitized events
KAFKA_CLEAN_EVENTS_TOPIC=ume-clean-events
# Consumer group used by projection engine
KAFKA_GROUP_ID=ume_client_group
```

Set `UME_DOSSIER_PATH` to change where UME stores user dossier files if you want to relocate them from the default location.

UME requires **Python 3.10** or newer. If your system Python is older than 3.10,
consider using [pyenv](https://github.com/pyenv/pyenv) or running in a
container image that provides a compatible Python version to ensure compatibility.
