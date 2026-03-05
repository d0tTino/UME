from __future__ import annotations

from ume.plugins.registry import (
    ConstructorMetadata,
    clear_plugins,
    list_plugins,
    register_lazy_plugin,
    register_plugin,
)


def test_list_plugins_filters_by_capability() -> None:
    clear_plugins()
    register_plugin("alpha", "one", lambda: 1)
    register_plugin("beta", "two", lambda: 2)

    alpha = list_plugins(capability="alpha")
    assert [item["name"] for item in alpha] == ["one"]
    assert alpha[0]["capability"] == "alpha"


def test_list_plugins_includes_lazy_metadata() -> None:
    clear_plugins()
    register_lazy_plugin(
        "graph_backend",
        "neo4j",
        lambda: (lambda _db_path: object()),
        metadata=ConstructorMetadata(source="builtin", lazy=True),
    )

    plugins = list_plugins(capability="graph_backend")
    assert plugins[0]["name"] == "neo4j"
    assert plugins[0]["metadata"].lazy is True


def test_plugin_metadata_exposes_capabilities() -> None:
    clear_plugins()
    register_plugin(
        "graph_backend",
        "postgres",
        lambda: 1,
        metadata=ConstructorMetadata(capabilities=frozenset({"transactional"})),
    )

    plugins = list_plugins(capability="graph_backend")
    assert plugins[0]["metadata"].capabilities == frozenset({"transactional"})
