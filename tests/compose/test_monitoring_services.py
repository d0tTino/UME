import subprocess
from pathlib import Path


def test_compose_includes_monitoring_services() -> None:
    compose_file = Path("docker/docker-compose.yml")
    out = subprocess.check_output([
        "docker-compose",
        "-f",
        str(compose_file),
        "config",
    ], text=True)
    assert "prometheus:" in out
    assert "grafana:" in out
