import json
import yaml
import pytest
from ume.graph_schema import GraphSchema, load_default_schema
from ume.processing import ProcessingError


def test_load_bad_json(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{ invalid")
    with pytest.raises(json.JSONDecodeError):
        GraphSchema.load(str(path))


def test_load_bad_yaml(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("foo: [1")
    with pytest.raises(yaml.YAMLError):
        GraphSchema.load(str(path))


def test_default_schema_node_properties():
    schema = load_default_schema()
    expected_node_properties = {
        "User": {"user_id", "name", "email", "created_at"},
        "UserGroup": {"group_id", "name", "members"},
        "CalendarEvent": {
            "event_id",
            "title",
            "start_time",
            "end_time",
            "description",
            "is_all_day",
            "location",
            "status",
            "rrule",
            "visibility",
        },
        "CalendarLayer": {"layer_id", "layer_name", "color"},
        "DecisionAnalysis": {"analysis_id", "query", "created_at"},
        "ProposedAction": {
            "action_id",
            "description",
            "rank",
            "is_optimal",
            "outcome_metrics",
        },
        "FinancialAccount": {
            "account_id",
            "account_type",
            "institution",
            "balance",
            "currency",
        },
    }

    assert set(schema.node_types) == set(expected_node_properties)
    for node_name, expected_properties in expected_node_properties.items():
        node = schema.node_types[node_name]
        assert set(node.properties) == expected_properties


@pytest.mark.parametrize(
    "node_def",
    [
        [],
        {"version": "1.0.0"},
        {"version": "1.0.0", "properties": []},
        {"version": "1.0.0", "properties": {"id": []}},
    ],
)
def test_load_malformed_node_type(tmp_path, node_def):
    schema_yaml = {
        "version": "1.0.0",
        "node_types": {"User": node_def},
        "edge_labels": {},
    }
    path = tmp_path / "schema.yaml"
    path.write_text(yaml.safe_dump(schema_yaml))
    with pytest.raises(ProcessingError):
        GraphSchema.load(str(path))


def test_validate_unknown_node_type():
    schema = load_default_schema()
    with pytest.raises(ProcessingError):
        schema.validate_node_type("UnknownType")


def test_validate_unknown_edge_label():
    schema = load_default_schema()
    with pytest.raises(ProcessingError):
        schema.validate_edge_label("UnknownLabel")


def test_get_edge_version():
    schema = load_default_schema()
    assert schema.get_edge_version("OWNED_BY") == "3.0.0"
    with pytest.raises(ProcessingError):
        schema.get_edge_version("UNKNOWN_LABEL")


def test_load_node_properties(tmp_path):
    schema_yaml = {
        "version": "1.0.0",
        "node_types": {
            "User": {
                "version": "1.0.0",
                "properties": {
                    "id": {"version": "1.0.0"},
                    "name": {"version": "1.0.0"},
                },
            }
        },
        "edge_labels": {},
    }
    path = tmp_path / "schema.yaml"
    path.write_text(yaml.safe_dump(schema_yaml))
    schema = GraphSchema.load(str(path))
    user = schema.node_types["User"]
    assert "id" in user.properties
    assert user.properties["id"].version == "1.0.0"


def test_load_misindented_schema(tmp_path):
    misindented_schema = """
version: "1.0.0"
node_types:
  User:
    version: "1.0.0"
    properties:
      id:
        version: "1.0.0"
      name:
      version: "1.0.0"
edge_labels: {}
"""

    path = tmp_path / "schema.yaml"
    path.write_text(misindented_schema)

    with pytest.raises(ProcessingError):
        GraphSchema.load(str(path))


def test_validate_node_property(tmp_path):
    schema_yaml = {
        "version": "1.0.0",
        "node_types": {
            "User": {
                "version": "1.0.0",
                "properties": {"id": {"version": "1.0.0"}},
            }
        },
        "edge_labels": {},
    }
    path = tmp_path / "schema.yaml"
    path.write_text(yaml.safe_dump(schema_yaml))
    schema = GraphSchema.load(str(path))
    schema.validate_node_property("User", "id")
    with pytest.raises(ProcessingError):
        schema.validate_node_property("User", "missing")


def test_edge_version_defaults(tmp_path):
    schema_yaml = {
        "version": "1.0.0",
        "node_types": {},
        "edge_labels": {"RELATES_TO": {}},
    }
    path = tmp_path / "schema.yaml"
    path.write_text(yaml.safe_dump(schema_yaml))
    schema = GraphSchema.load(str(path))
    assert schema.get_edge_version("RELATES_TO") == "0.0.0"

