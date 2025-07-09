# ruff: noqa: E402
import json
import pytest
yaml = pytest.importorskip("yaml")
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

