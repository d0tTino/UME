# mypy: ignore-errors
class DockerContainer:
    def __init__(self, image: str = ""):
        self.image = image
        self._ports = []
        self._command = None
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc, tb):
        pass
    def with_exposed_ports(self, *ports):
        self._ports.extend(ports)
        return self
    def with_command(self, command: str):
        self._command = command
        return self
    def start(self):
        return self
    def stop(self):
        pass
    def get_container_host_ip(self) -> str:
        return "127.0.0.1"
    def get_exposed_port(self, port: int) -> str:
        return str(port)
    def get_bootstrap_server(self) -> str:
        return "localhost:9092"
