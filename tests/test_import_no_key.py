import importlib
import sys
import pytest


def test_import_without_key(monkeypatch):
    monkeypatch.delenv("UME_AUDIT_SIGNING_KEY", raising=False)
    sys.modules.pop("ume", None)
    sys.modules.pop("ume.config", None)
    with pytest.raises(ValueError):
        importlib.import_module("ume")
    # Restore for other tests
    monkeypatch.setenv("UME_AUDIT_SIGNING_KEY", "test-key")
    sys.modules.pop("ume", None)
    importlib.import_module("ume")
