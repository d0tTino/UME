import importlib
import sys
import pytest


def test_import_without_key(monkeypatch, tmp_path):
    monkeypatch.setenv("UME_ENV", "production")
    monkeypatch.delenv("UME_AUDIT_SIGNING_KEY", raising=False)
    monkeypatch.setenv("UME_API_TOKEN", "token")
    monkeypatch.setenv("UME_OAUTH_PASSWORD", "super-secret")
    monkeypatch.chdir(tmp_path)
    sys.modules.pop("ume", None)
    sys.modules.pop("ume.config", None)
    with pytest.raises(ValueError):
        importlib.import_module("ume")
    # Restore for other tests
    monkeypatch.setenv("UME_AUDIT_SIGNING_KEY", "test-key")
    sys.modules.pop("ume", None)
    importlib.import_module("ume")
