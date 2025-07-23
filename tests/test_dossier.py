from ume.dossier import (
    Dossier,
    add_reflection,
    list_projects,
    update_preferences,
)


def test_dossier_init_and_helpers(tmp_path):
    dossier = Dossier.init_dossier(tmp_path)
    assert dossier.schema_version == Dossier.schema_version

    dossier.projects.append({"name": "demo"})
    dossier.save()

    add_reflection(dossier, "thinking")
    update_preferences(dossier, theme="dark")

    reloaded = Dossier.load(tmp_path)
    assert list_projects(reloaded) == ["demo"]
    assert reloaded.preferences["theme"] == "dark"
    assert reloaded.reflections[0]["text"] == "thinking"


def test_dossier_env_load(tmp_path, monkeypatch):
    Dossier.init_dossier(tmp_path)
    monkeypatch.setenv("UME_DOSSIER_PATH", str(tmp_path))
    dossier = Dossier.load()
    assert dossier.root == tmp_path
