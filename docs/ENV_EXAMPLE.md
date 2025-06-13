# Example .env

The `.env` file allows you to override default settings defined in `src/ume/config.py`. Values in this file are loaded before reading your shell environment.

```bash
# Path where the CLI stores its SQLite database
UME_CLI_DB=./ume.db

# Location for audit log entries
UME_AUDIT_LOG_PATH=./audit.log

# Token used by the API server for authentication
UME_API_TOKEN=secret-token

# Optional role for the CLI (leave unset for full permissions)
UME_ROLE=view-only
```

UME requires **Python 3.12**. If your system Python is older than 3.12,
consider using [pyenv](https://github.com/pyenv/pyenv) or running in a
container image that provides Python 3.12 to ensure compatibility.
