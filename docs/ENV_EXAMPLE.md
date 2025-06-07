# Example .env

The `.env` file allows you to override default settings defined in `src/ume/config.py`. Values in this file are loaded before reading your shell environment.

```bash
# Path where the CLI stores its SQLite database
UME_CLI_DB=./ume.db

# Location for audit log entries
UME_AUDIT_LOG_PATH=./audit.log

# Token used by the API server for authentication
UME_API_TOKEN=secret-token
```
