from pathlib import Path


def test_compose_graph_consumer_uses_projection_worker() -> None:
    compose_text = Path("docker/docker-compose.yml").read_text()
    assert "command: poetry run python -m ume.services.projection_worker" in compose_text
    assert "consumer_demo.py" not in compose_text


def test_compose_includes_graph_smoke_check() -> None:
    compose_text = Path("docker/docker-compose.yml").read_text()
    assert "graph-smoke-check:" in compose_text
    assert "examples/compose_projection_smoke_check.py" in compose_text
