import os

import pytest
from cryptography.fernet import Fernet

import ume.event_ledger as event_module



def _get_class():
    return event_module.EventLedger


def test_encrypted_ledger_roundtrip(tmp_path, monkeypatch):
    key = Fernet.generate_key().decode()
    from ume import config as cfg
    monkeypatch.setattr(
        cfg.settings, "UME_ENCRYPTION_ENABLED", True, raising=False
    )
    monkeypatch.setattr(cfg.settings, "UME_ENCRYPTION_KEY", key, raising=False)
    monkeypatch.setattr(
        event_module, "settings", cfg.settings, raising=False
    )
    EventLedgerCls = _get_class()
    ledger_path = tmp_path / "ledger.db"
    ledger = EventLedgerCls(str(ledger_path))
    ledger.append(0, {"foo": "bar"})
    ledger.close()

    raw = ledger_path.read_bytes()
    assert b"foo" not in raw

    ledger2 = EventLedgerCls(str(ledger_path))
    assert ledger2.range() == [(0, {"foo": "bar"})]
    ledger2.close()


def test_encrypted_ledger_atomic_replace_failure(tmp_path, monkeypatch):
    key = Fernet.generate_key().decode()
    from ume import config as cfg
    monkeypatch.setattr(cfg.settings, "UME_ENCRYPTION_ENABLED", True, raising=False)
    monkeypatch.setattr(cfg.settings, "UME_ENCRYPTION_KEY", key, raising=False)
    monkeypatch.setattr(event_module, "settings", cfg.settings, raising=False)
    EventLedgerCls = _get_class()
    ledger_path = tmp_path / "ledger.db"
    ledger = EventLedgerCls(str(ledger_path))
    ledger.append(0, {"foo": "bar"})

    def fail_replace(src: str, dst: str) -> None:
        raise RuntimeError("boom")

    orig_replace = os.replace
    monkeypatch.setattr(os, "replace", fail_replace)
    with pytest.raises(RuntimeError):
        ledger.close()
    monkeypatch.setattr(os, "replace", orig_replace)

    assert not ledger_path.exists()

    EventLedgerCls = _get_class()
    ledger2 = EventLedgerCls(str(ledger_path))
    assert ledger2.range() == [(0, {"foo": "bar"})]
    ledger2.close()


def test_encrypted_ledger_cleanup_failure(tmp_path, monkeypatch):
    key = Fernet.generate_key().decode()
    from ume import config as cfg
    monkeypatch.setattr(cfg.settings, "UME_ENCRYPTION_ENABLED", True, raising=False)
    monkeypatch.setattr(cfg.settings, "UME_ENCRYPTION_KEY", key, raising=False)
    monkeypatch.setattr(event_module, "settings", cfg.settings, raising=False)
    EventLedgerCls = _get_class()
    ledger_path = tmp_path / "ledger.db"
    ledger = EventLedgerCls(str(ledger_path))
    ledger.append(0, {"foo": "bar"})

    orig_remove = os.remove

    def fail_remove(path: str) -> None:
        if path.endswith(".dec"):
            raise RuntimeError("boom")
        orig_remove(path)

    monkeypatch.setattr(os, "remove", fail_remove)
    with pytest.raises(RuntimeError):
        ledger.close()
    monkeypatch.setattr(os, "remove", orig_remove)

    assert ledger_path.exists()

    EventLedgerCls = _get_class()
    ledger2 = EventLedgerCls(str(ledger_path))
    assert ledger2.range() == [(0, {"foo": "bar"})]
    ledger2.close()
