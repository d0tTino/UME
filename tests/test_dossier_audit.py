import importlib
import os

import ume
from ume.config import settings
from ume.dossier import Dossier, add_project, list_projects


def test_dossier_helper_audit(tmp_path, monkeypatch):
    monkeypatch.setenv("UME_AUDIT_LOG_PATH", str(tmp_path / "audit.log"))
    monkeypatch.setenv("UME_AGENT_ID", "tester")

    importlib.reload(ume.config)
    importlib.reload(ume.audit)
    importlib.reload(ume.dossier)

    monkeypatch.setattr(settings, "UME_DOSSIER_PATH", str(tmp_path), raising=False)

    dossier = Dossier.init_dossier(tmp_path / "d1")
    open(os.environ["UME_AUDIT_LOG_PATH"], "w").close()
    start = len(ume.audit.get_audit_entries())

    add_project(dossier, "p1")
    list_projects(dossier)

    entries = ume.audit.get_audit_entries()[start:]
    assert any("add_project" in e["reason"] for e in entries)
    assert any("list_projects" in e["reason"] for e in entries)
