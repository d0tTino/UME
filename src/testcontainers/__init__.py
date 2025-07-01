# mypy: ignore-errors
"""Minimal testcontainers implementation for Docker-based tests."""

from __future__ import annotations

class DockerContainer:
    def __init__(self, image: str = "") -> None:
        self.image = image
    def __enter__(self) -> "DockerContainer":
        return self
    def __exit__(self, exc_type, exc, tb) -> None:
        pass
    def start(self) -> "DockerContainer":
        return self
    def get_bootstrap_server(self) -> str:
        return "localhost:9092"

class KafkaContainer(DockerContainer):
    def get_bootstrap_server(self) -> str:
        return "localhost:9092"

__all__ = [
    "DockerContainer",
    "KafkaContainer",
]
