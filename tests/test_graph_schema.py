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


def test_validate_unknown_node_type():
    schema = load_default_schema()
    with pytest.raises(ProcessingError):
        schema.validate_node_type("UnknownType")


def test_validate_unknown_edge_label():
    schema = load_default_schema()
    with pytest.raises(ProcessingError):
        schema.validate_edge_label("UnknownLabel")


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

