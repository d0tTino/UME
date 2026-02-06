from ume.graph_mutations import add_edge_with_schema_validation, add_node_with_schema_validation
from ume.graph_schema import EdgeLabel, GraphSchema, NodeType, Property
from ume.processing import ProcessingError


class StubGraph:
    def __init__(self) -> None:
        self.nodes = {}
        self.edges = []

    def add_node(self, node_id, attrs):
        self.nodes[node_id] = attrs

    def add_edge(self, src, tgt, label, attrs=None, schema_version=None):
        self.edges.append((src, tgt, label, attrs, schema_version))


def _schema() -> GraphSchema:
    return GraphSchema(
        version="9.0.0",
        node_types={
            "User": NodeType(
                name="User",
                version="9.1.0",
                properties={
                    "type": Property(name="type", version="9.1.0"),
                    "user_id": Property(name="user_id", version="9.1.0"),
                },
            )
        },
        edge_labels={
            "OWNED_BY": EdgeLabel(label="OWNED_BY", version="9.2.0")
        },
    )


def test_add_node_with_schema_validation_applies_expected_version():
    graph = StubGraph()
    attrs = add_node_with_schema_validation(
        graph,
        "u1",
        {"type": "User", "user_id": "u1"},
        schema=_schema(),
    )

    assert attrs["schema_version"] == "9.1.0"
    assert graph.nodes["u1"]["schema_version"] == "9.1.0"


def test_add_edge_with_schema_validation_applies_expected_version():
    graph = StubGraph()
    version = add_edge_with_schema_validation(
        graph,
        "n1",
        "n2",
        "OWNED_BY",
        {"permission_level": "editor"},
        schema=_schema(),
    )

    assert version == "9.2.0"
    assert graph.edges[0][4] == "9.2.0"


def test_add_edge_with_schema_validation_rejects_wrong_version():
    graph = StubGraph()
    try:
        add_edge_with_schema_validation(
            graph,
            "n1",
            "n2",
            "OWNED_BY",
            None,
            schema=_schema(),
            schema_version="1.0.0",
        )
    except ProcessingError as exc:
        assert "schema_version does not match" in str(exc)
    else:
        raise AssertionError("Expected ProcessingError")
