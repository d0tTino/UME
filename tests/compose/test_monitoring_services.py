from pathlib import Path
import yaml


def test_compose_includes_monitoring_services() -> None:
    compose_file = Path("docker/docker-compose.yml")
    config = yaml.safe_load(compose_file.read_text())
    services = config.get("services", {})
    assert "prometheus" in services
    assert "grafana" in services
