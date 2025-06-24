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
