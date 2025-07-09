import pytest

from ume.config.loader import load_settings


def test_audit_key_default_raises(monkeypatch):
    monkeypatch.setenv("UME_AUDIT_SIGNING_KEY", "default-key")
    load_settings.cache_clear()
    with pytest.raises(ValueError):
        load_settings()


def test_audit_key_custom(monkeypatch):
    monkeypatch.setenv("UME_AUDIT_SIGNING_KEY", "mykey")
    load_settings.cache_clear()
    s = load_settings()
    assert s.UME_AUDIT_SIGNING_KEY == "mykey"


def test_rate_limit_default(monkeypatch):
    monkeypatch.delenv("UME_RATE_LIMIT_REDIS", raising=False)
    load_settings.cache_clear()
    s = load_settings()
    assert s.UME_RATE_LIMIT_REDIS is None


def test_rate_limit_env(monkeypatch):
    monkeypatch.setenv("UME_RATE_LIMIT_REDIS", "redis://localhost:6379/0")
    load_settings.cache_clear()
    s = load_settings()
    assert s.UME_RATE_LIMIT_REDIS == "redis://localhost:6379/0"
