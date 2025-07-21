from __future__ import annotations

from pathlib import Path

import importlib
import sys
import pytest


def test_env_file_created(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from ume.cli import compose

    importlib.reload(compose)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(compose.secrets, "token_hex", lambda *_: "new-key")

    compose._ensure_env_file()

    env_file = tmp_path / ".env"
    assert env_file.exists()
    content = env_file.read_text()
    assert "UME_AUDIT_SIGNING_KEY=new-key" in content

    out = capsys.readouterr().out
    assert "Created .env from env.example" in out
    assert "insecure default key" not in out


def test_env_file_replaced_with_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from ume.cli import compose

    env_file = tmp_path / ".env"
    env_file.write_text(
        "UME_AUDIT_SIGNING_KEY=default-key\n"  # pragma: allowlist secret
    )

    importlib.reload(compose)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(compose.secrets, "token_hex", lambda *_: "new-key")

    compose._ensure_env_file()

    assert "UME_AUDIT_SIGNING_KEY=new-key" in env_file.read_text()

    out = capsys.readouterr().out
    assert "insecure default key" in out
    assert "Updated secrets in .env with secure values" in out


def test_env_file_replaced_without_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from ume.cli import compose

    env_file = tmp_path / ".env"
    env_file.write_text(
        "UME_AUDIT_SIGNING_KEY=old-key\n"  # pragma: allowlist secret
    )

    importlib.reload(compose)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(compose.secrets, "token_hex", lambda *_: "new-key")

    compose._ensure_env_file()

    assert "UME_AUDIT_SIGNING_KEY=new-key" in env_file.read_text()

    out = capsys.readouterr().out
    assert "insecure default key" not in out
    assert "Updated secrets in .env with secure values" in out


def test_quickstart_regenerates_env_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """``quickstart`` should regenerate ``.env`` when defaults are present."""
    import importlib
    import ume_cli as cli
    from ume.cli import compose

    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "UME_AUDIT_SIGNING_KEY=default-key",  # pragma: allowlist secret
                "UME_OAUTH_PASSWORD=password",  # pragma: allowlist secret
            ]
        )
        + "\n"
    )

    importlib.reload(cli)
    importlib.reload(compose)

    tokens = iter(["new-key", "new-pass"])

    def fake_run(cmd: list[str], check: bool = True, **_: object) -> None:
        pass

    def fake_check_output(cmd: list[str], **_: object) -> str:
        if "ps" in cmd:
            return "redpanda healthy\nneo4j healthy\nume-api healthy\n"
        return ""

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(compose.subprocess, "run", fake_run)
    monkeypatch.setattr(compose.subprocess, "check_output", fake_check_output)
    monkeypatch.setattr(compose.time, "sleep", lambda *_: None)
    monkeypatch.setattr(compose.secrets, "token_hex", lambda *_: next(tokens))

    argv = sys.argv[:]
    sys.argv = ["ume-cli", "quickstart", "--no-confirm"]
    cli.main()
    sys.argv = argv

    out = capsys.readouterr().out
    content = env_file.read_text()
    assert "UME_AUDIT_SIGNING_KEY=new-key" in content
    assert "UME_OAUTH_PASSWORD=new-pass" in content
    assert "Regenerating .env with secure defaults" in out
