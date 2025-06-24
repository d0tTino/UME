import pytest

from ume.config import Settings


def test_audit_key_default_raises(monkeypatch):
    monkeypatch.setenv("UME_AUDIT_SIGNING_KEY", "default-key")
    with pytest.raises(ValueError):
        Settings()


def test_audit_key_custom(monkeypatch):
    monkeypatch.setenv("UME_AUDIT_SIGNING_KEY", "mykey")
    s = Settings()
    assert s.UME_AUDIT_SIGNING_KEY == "mykey"


def test_rate_limit_default(monkeypatch):
    monkeypatch.delenv("UME_RATE_LIMIT_REDIS", raising=False)
    s = Settings()
    assert s.UME_RATE_LIMIT_REDIS is None


def test_rate_limit_env(monkeypatch):
    monkeypatch.setenv("UME_RATE_LIMIT_REDIS", "redis://localhost:6379/0")
    s = Settings()
    assert s.UME_RATE_LIMIT_REDIS == "redis://localhost:6379/0"
