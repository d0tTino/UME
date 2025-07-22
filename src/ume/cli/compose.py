from __future__ import annotations

import os
import secrets
import subprocess
import sys
import time
from pathlib import Path
import shutil

# Ensure local package import when run directly without installation
_src_path = Path(__file__).resolve().parents[3] / "src"
if _src_path.exists() and str(_src_path) not in sys.path:
    sys.path.insert(0, str(_src_path))

ROOT_DIR = Path(__file__).resolve().parents[3]
COMPOSE_FILE = ROOT_DIR / "docker" / "docker-compose.yml"


def _require_docker() -> None:
    """Exit with a message if Docker is not available."""
    if os.getenv("UME_SKIP_DOCKER_CHECK") == "1":
        return
    if shutil.which("docker") is None:
        print(
            "Docker is required to run the UME stack. "
            "Please install Docker and ensure it is on your PATH."
        )
        raise SystemExit(1)


def _require_npm() -> None:
    """Exit with a message if npm (Node.js) is not available."""
    if os.getenv("UME_SKIP_NPM_CHECK") == "1":
        return
    if shutil.which("npm") is None:
        print("npm is required to build the dashboard. Please install Node.js.")
        raise SystemExit(1)


def _compose_up(compose_file: Path = COMPOSE_FILE, timeout: int = 120) -> None:
    """Start Docker Compose services and wait until healthy."""
    _require_docker()
    try:
        subprocess.run(
            ["docker", "compose", "-f", str(compose_file), "up", "-d"],
            check=True,
        )
    except FileNotFoundError as exc:
        print("Docker is not installed or not on PATH")
        raise SystemExit(1) from exc

    required = {"redpanda", "ume-api"}
    try:
        if "neo4j" in compose_file.read_text():
            required.add("neo4j")
    except OSError:
        pass
    start = time.time()
    while time.time() - start < timeout:
        out = subprocess.check_output(
            [
                "docker",
                "compose",
                "-f",
                str(compose_file),
                "ps",
                "--format",
                "{{.Name}} {{.Health}}",
            ],
            text=True,
        )
        statuses = {
            name: status
            for name, status in (
                line.split(maxsplit=1) for line in out.splitlines() if line.strip()
            )
        }
        if all(statuses.get(svc) == "healthy" for svc in required):
            break
        time.sleep(5)
    else:
        print("Timed out waiting for services to become healthy.")

    print("Stack running. API docs: http://localhost:8000/docs")
    print("Recall endpoint: http://localhost:8000/recall")
    print("Graph snapshot endpoints: http://localhost:8000/snapshot")


def _compose_down(compose_file: Path = COMPOSE_FILE) -> None:
    """Stop Docker Compose services."""
    _require_docker()
    try:
        subprocess.run(
            ["docker", "compose", "-f", str(compose_file), "down"],
            check=True,
        )
    except FileNotFoundError as exc:
        print("Docker is not installed or not on PATH")
        raise SystemExit(1) from exc
    print("Stack stopped.")


def _compose_ps(compose_file: Path = COMPOSE_FILE) -> None:
    """Print Docker Compose service health info."""
    _require_docker()
    try:
        out = subprocess.check_output(
            [
                "docker",
                "compose",
                "-f",
                str(compose_file),
                "ps",
                "--format",
                "{{.Name}} {{.Health}}",
            ],
            text=True,
        )
    except FileNotFoundError as exc:
        print("Docker is not installed or not on PATH")
        raise SystemExit(1) from exc
    if not out.strip():
        print("No running containers.")
        return
    for line in out.splitlines():
        if line.strip():
            name, health = line.split(maxsplit=1)
            print(f"{name}: {health}")


def _ensure_env_file(env_file: Path = Path(".env")) -> None:
    """Create ``.env`` if missing and populate secure defaults."""
    created = False
    if env_file.exists():
        env_lines = env_file.read_text().splitlines()
    else:
        example = ROOT_DIR / "env.example"
        try:
            env_lines = example.read_text().splitlines()
        except FileNotFoundError:
            return
        created = True

    new_key = secrets.token_hex(32)
    new_pass = secrets.token_hex(16)
    prev_key: str | None = None
    replaced_key = False
    replaced_pass = False
    for i, line in enumerate(env_lines):
        if line.startswith("UME_AUDIT_SIGNING_KEY="):
            prev_key = line.split("=", 1)[1]
            env_lines[i] = f"UME_AUDIT_SIGNING_KEY={new_key}"
            replaced_key = True
        elif line.startswith("UME_OAUTH_PASSWORD="):
            env_lines[i] = f"UME_OAUTH_PASSWORD={new_pass}"
            replaced_pass = True

    if not replaced_key:
        env_lines.append(f"UME_AUDIT_SIGNING_KEY={new_key}")
    if not replaced_pass:
        env_lines.append(f"UME_OAUTH_PASSWORD={new_pass}")

    env_content = "\n".join(env_lines) + "\n"
    env_file.write_text(env_content)

    if prev_key == "default-key":
        print(
            "WARNING: UME_AUDIT_SIGNING_KEY uses the insecure default key. "
            "Edit .env and set a unique value."
        )

    if created:
        print(
            "Created .env from env.example with random UME_AUDIT_SIGNING_KEY "
            "and UME_OAUTH_PASSWORD"
        )
    elif replaced_key or replaced_pass:
        print("Updated secrets in .env with secure values")


def _quickstart(no_confirm: bool = False, force_build: bool = False) -> None:
    """Prepare environment and start the Docker Compose stack."""
    _require_docker()
    _require_npm()
    env_file = Path(".env")
    if not no_confirm and not sys.stdin.isatty():
        no_confirm = True
    content = env_file.read_text() if env_file.exists() else ""
    if (
        not env_file.exists()
        or "UME_AUDIT_SIGNING_KEY=default-key" in content
        or "UME_OAUTH_PASSWORD=password" in content
    ):
        if env_file.exists():
            print("Regenerating .env with secure defaults")
        else:
            print("Creating .env with secure defaults")
        _ensure_env_file(env_file)
    cert_script = ROOT_DIR / "docker" / "generate-certs.sh"
    cert_dir = cert_script.parent / "certs"
    if not no_confirm and not any(cert_dir.glob("*.crt")):
        resp = input("Generate TLS certificates in docker/certs/? [y/N]: ")
        if resp.lower() != "y":
            print("Aborted.")
            return
    subprocess.run(["bash", str(cert_script)], check=True)

    frontend_dir = ROOT_DIR / "frontend"
    need_install = force_build or not (frontend_dir / "node_modules").exists()
    need_build = force_build or not (frontend_dir / "dist").exists()
    try:
        if need_install:
            print("Installing frontend dependencies...")
            subprocess.run(["npm", "install"], cwd=frontend_dir, check=True)
        if need_build:
            print("Building frontend dashboard...")
            subprocess.run(["npm", "run", "build"], cwd=frontend_dir, check=True)
    except FileNotFoundError:
        print("npm is required to build the dashboard. Please install Node.js.")

    _compose_up()
