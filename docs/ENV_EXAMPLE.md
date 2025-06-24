# Example .env

The `.env` file allows you to override default settings defined in `src/ume/config.py`. Values in this file are loaded before reading your shell environment.

```bash
# Path where the CLI stores its SQLite database
UME_CLI_DB=./ume.db

# Location for audit log entries
UME_AUDIT_LOG_PATH=./audit.log

# Key used to sign audit entries. Must be changed from the default.
UME_AUDIT_SIGNING_KEY=<your-key>

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
```

UME requires **Python 3.10** or newer. If your system Python is older than 3.10,
consider using [pyenv](https://github.com/pyenv/pyenv) or running in a
container image that provides a compatible Python version to ensure compatibility.
