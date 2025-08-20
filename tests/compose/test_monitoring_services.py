from pathlib import Path


def test_compose_includes_monitoring_services() -> None:
    compose_text = Path("docker/docker-compose.yml").read_text()
    assert "prometheus:" in compose_text
    assert "grafana:" in compose_text
