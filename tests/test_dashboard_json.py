import json
from pathlib import Path
from jsonschema import validate

SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "panels": {"type": "array"},
    },
    "required": ["title", "panels"],
}


def test_dashboard_json_valid() -> None:
    data = json.loads(Path("docs/grafana/ume_dashboard.json").read_text())
    validate(data, SCHEMA)
