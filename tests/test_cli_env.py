from __future__ import annotations

from pathlib import Path

import importlib
import pytest


def test_env_file_created(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import ume_cli as cli

    importlib.reload(cli)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli.secrets, "token_hex", lambda *_: "new-key")

    cli._ensure_env_file()

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
    import ume_cli as cli

    env_file = tmp_path / ".env"
    env_file.write_text(
        "UME_AUDIT_SIGNING_KEY=default-key\n"  # pragma: allowlist secret
    )

    importlib.reload(cli)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli.secrets, "token_hex", lambda *_: "new-key")

    cli._ensure_env_file()

    assert "UME_AUDIT_SIGNING_KEY=new-key" in env_file.read_text()

    out = capsys.readouterr().out
    assert "insecure default key" in out
    assert "Replaced UME_AUDIT_SIGNING_KEY in .env" in out


def test_env_file_replaced_without_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import ume_cli as cli

    env_file = tmp_path / ".env"
    env_file.write_text(
        "UME_AUDIT_SIGNING_KEY=old-key\n"  # pragma: allowlist secret
    )

    importlib.reload(cli)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli.secrets, "token_hex", lambda *_: "new-key")

    cli._ensure_env_file()

    assert "UME_AUDIT_SIGNING_KEY=new-key" in env_file.read_text()

    out = capsys.readouterr().out
    assert "insecure default key" not in out
    assert "Replaced UME_AUDIT_SIGNING_KEY in .env" in out
