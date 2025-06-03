# src/ume/config.py
import os
from pathlib import Path

# Default snapshot path for the CLI
# Ensures the .ume directory exists in the user's home.
# Note: Directory creation at definition time might be too early if CLI/API isn't run by user.
# It's better to ensure directory exists when saving the snapshot.
# For now, just define the path.
_cli_home_dir = Path(os.path.expanduser("~"))
CLI_SNAPSHOT_DIR = _cli_home_dir / ".ume"
CLI_SNAPSHOT_PATH = CLI_SNAPSHOT_DIR / "ume_graph.json"

# Default snapshot path for the API
# Allows override via UME_SNAPSHOT_PATH environment variable,
# otherwise defaults to "ume_graph.json" in the current working directory.
API_SNAPSHOT_FILENAME = "ume_graph.json"
API_SNAPSHOT_PATH_STR = os.getenv("UME_SNAPSHOT_PATH", API_SNAPSHOT_FILENAME)
API_SNAPSHOT_PATH = Path(API_SNAPSHOT_PATH_STR)

# It might be useful to also have a function to ensure path exists before writing
# def ensure_path_exists(path: Path):
#     path.parent.mkdir(parents=True, exist_ok=True)
# This logic will be incorporated into snapshot_graph_to_file instead.
```
