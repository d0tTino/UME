# mypy: ignore-errors

class DockerCompose:
    def __init__(self, path: str = "", compose_file_name: str = "docker-compose.yaml"):
        self.path = path
        self.compose_file_name = compose_file_name
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc, tb):
        pass
    def start(self):
        return self
