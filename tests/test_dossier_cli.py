import os
import sys
import json
import subprocess
from pathlib import Path

CLI_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "ume_cli.py"

SITECUSTOMIZE = """
import os, json, atexit, sys, types
from fastapi import FastAPI
from starlette.testclient import TestClient
import httpx

ume_pkg = types.ModuleType('ume')
sys.modules.setdefault('ume', ume_pkg)
sys.modules['ume.cli'] = types.ModuleType('ume.cli')
compose_mod = types.ModuleType('ume.cli.compose')
compose_mod._compose_down = lambda *a, **k: None
compose_mod._compose_ps = lambda *a, **k: None
compose_mod._quickstart = lambda *a, **k: None
sys.modules['ume.cli.compose'] = compose_mod
prompt_mod = types.ModuleType('ume.cli.prompt')
prompt_mod.UMEPrompt = object
prompt_mod.create_graph_adapter = lambda *a, **k: None
sys.modules['ume.cli.prompt'] = prompt_mod
log_mod = types.ModuleType('ume.logging_utils')
log_mod.configure_logging = lambda: None
sys.modules['ume.logging_utils'] = log_mod
cfg_mod = types.ModuleType('ume.config')
class Settings:
    UME_API_TOKEN = ''
    UME_CLI_DB = ':memory:'
settings = Settings()
cfg_mod.settings = settings
sys.modules['ume.config'] = cfg_mod

logs = []
app = FastAPI()

@app.get('/dossier/{dossier_id}')
async def view_dossier(dossier_id: str):
    return {'id': dossier_id}

@app.post('/dossier/add-project')
async def add_project(payload: dict):
    return {'dossier_id': payload['dossier_id'], 'project_id': payload['project_id']}

@app.post('/dossier/add-reflection')
async def add_reflection(payload: dict):
    return {'dossier_id': payload['dossier_id'], 'reflection': payload['text']}

@app.post('/dossier/add-memory')
async def add_memory(payload: dict):
    return {'dossier_id': payload['dossier_id'], 'memory': payload['text']}

@app.post('/dossier/set-pref')
async def set_pref(payload: dict):
    return {'dossier_id': payload['dossier_id'], 'key': payload['key'], 'value': payload['value']}

@app.post('/dossier/add-value')
async def add_value(payload: dict):
    return {'dossier_id': payload['dossier_id'], 'value': payload['value']}

@app.post('/dossier/add-skill')
async def add_skill(payload: dict):
    return {'dossier_id': payload['dossier_id'], 'skill': payload['skill']}

@app.get('/dossier/projects/{dossier_id}')
async def list_projects(dossier_id: str):
    return {'dossier_id': dossier_id, 'projects': ['p1']}

@app.get('/dossier/reflections/{dossier_id}')
async def list_reflections(dossier_id: str):
    return {'dossier_id': dossier_id, 'reflections': ['r1']}

@app.get('/dossier/skills/{dossier_id}')
async def list_skills(dossier_id: str):
    return {'dossier_id': dossier_id, 'skills': ['s1']}

@app.get('/dossier/memories/{dossier_id}')
async def list_memories(dossier_id: str):
    return {'dossier_id': dossier_id, 'memories': ['m1']}

@app.post('/dossier/snapshot')
async def snapshot(payload: dict):
    return {'dossier_id': payload['dossier_id'], 'path': '/d/h'}

client = TestClient(app)

def _wrap(method):
    func = getattr(client, method)
    def wrapper(url, *args, **kwargs):
        logs.append({'method': method.upper(), 'url': url, 'json': kwargs.get('json')})
        return func(url, *args, **kwargs)
    return wrapper

httpx.get = _wrap('get')
httpx.post = _wrap('post')

@atexit.register
def _dump():
    path = os.environ.get('REQ_LOG')
    if path:
        with open(path, 'w') as f:
            json.dump(logs, f)
"""


def _run_cli(tmp_path: Path, args: list[str]):
    (tmp_path / "sitecustomize.py").write_text(SITECUSTOMIZE)
    log = tmp_path / "log.json"
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{tmp_path}{os.pathsep}" + env.get("PYTHONPATH", "")
    env["REQ_LOG"] = str(log)
    env.pop("PYTHONHOME", None)
    proc = subprocess.run(
        [sys.executable, str(CLI_SCRIPT_PATH)] + args,
        capture_output=True,
        text=True,
        env=env,
    )
    requests = json.loads(log.read_text())
    return proc, requests


def test_dossier_view(tmp_path: Path):
    proc, requests = _run_cli(tmp_path, ["dossier", "view", "d1"])
    assert proc.returncode == 0
    assert json.loads(proc.stdout) == {"id": "d1"}
    assert requests == [
        {"method": "GET", "url": "http://localhost:8000/dossier/d1", "json": None}
    ]


def test_dossier_add_project(tmp_path: Path):
    proc, requests = _run_cli(tmp_path, ["dossier", "add-project", "d1", "p1"])
    assert proc.returncode == 0
    assert json.loads(proc.stdout) == {"dossier_id": "d1", "project_id": "p1"}
    assert requests == [
        {
            "method": "POST",
            "url": "http://localhost:8000/dossier/add-project",
            "json": {"dossier_id": "d1", "project_id": "p1"},
        }
    ]


def test_dossier_add_reflection(tmp_path: Path):
    proc, requests = _run_cli(
        tmp_path, ["dossier", "add-reflection", "d2", "thinking"]
    )
    assert proc.returncode == 0
    assert json.loads(proc.stdout) == {
        "dossier_id": "d2",
        "reflection": "thinking",
    }
    assert requests == [
        {
            "method": "POST",
            "url": "http://localhost:8000/dossier/add-reflection",
            "json": {"dossier_id": "d2", "text": "thinking"},
        }
    ]


def test_dossier_add_memory(tmp_path: Path):
    proc, requests = _run_cli(
        tmp_path, ["dossier", "add-memory", "d2", "fact"]
    )
    assert proc.returncode == 0
    assert json.loads(proc.stdout) == {
        "dossier_id": "d2",
        "memory": "fact",
    }
    assert requests == [
        {
            "method": "POST",
            "url": "http://localhost:8000/dossier/add-memory",
            "json": {"dossier_id": "d2", "text": "fact"},
        }
    ]


def test_dossier_set_pref(tmp_path: Path):
    proc, requests = _run_cli(
        tmp_path, ["dossier", "set-pref", "d3", "theme", "dark"]
    )
    assert proc.returncode == 0
    assert json.loads(proc.stdout) == {
        "dossier_id": "d3",
        "key": "theme",
        "value": "dark",
    }
    assert requests == [
        {
            "method": "POST",
            "url": "http://localhost:8000/dossier/set-pref",
            "json": {"dossier_id": "d3", "key": "theme", "value": "dark"},
        }
    ]


def test_dossier_add_value(tmp_path: Path):
    proc, requests = _run_cli(tmp_path, ["dossier", "add-value", "d4", "honesty"])
    assert proc.returncode == 0
    assert json.loads(proc.stdout) == {"dossier_id": "d4", "value": "honesty"}
    assert requests == [
        {
            "method": "POST",
            "url": "http://localhost:8000/dossier/add-value",
            "json": {"dossier_id": "d4", "value": "honesty"},
        }
    ]


def test_dossier_add_skill(tmp_path: Path):
    proc, requests = _run_cli(tmp_path, ["dossier", "add-skill", "d5", "python"])
    assert proc.returncode == 0
    assert json.loads(proc.stdout) == {"dossier_id": "d5", "skill": "python"}
    assert requests == [
        {
            "method": "POST",
            "url": "http://localhost:8000/dossier/add-skill",
            "json": {"dossier_id": "d5", "skill": "python"},
        }
    ]


def test_dossier_list_skills(tmp_path: Path):
    proc, requests = _run_cli(tmp_path, ["dossier", "list-skills", "d6"])
    assert proc.returncode == 0
    assert json.loads(proc.stdout) == {"dossier_id": "d6", "skills": ["s1"]}
    assert requests == [
        {
            "method": "GET",
            "url": "http://localhost:8000/dossier/skills/d6",
            "json": None,
        }
    ]


def test_dossier_list_memories(tmp_path: Path):
    proc, requests = _run_cli(tmp_path, ["dossier", "list-memories", "d8"])
    assert proc.returncode == 0
    assert json.loads(proc.stdout) == {"dossier_id": "d8", "memories": ["m1"]}
    assert requests == [
        {
            "method": "GET",
            "url": "http://localhost:8000/dossier/memories/d8",
            "json": None,
        }
    ]


def test_dossier_snapshot(tmp_path: Path):
    proc, requests = _run_cli(tmp_path, ["dossier", "snapshot", "d7"])
    assert proc.returncode == 0
    assert json.loads(proc.stdout) == {"dossier_id": "d7", "path": "/d/h"}
    assert requests == [
        {
            "method": "POST",
            "url": "http://localhost:8000/dossier/snapshot",
            "json": {"dossier_id": "d7"},
        }
    ]


def test_dossier_add_skill_and_list(tmp_path: Path):
    proc1, req1 = _run_cli(tmp_path, ["dossier", "add-skill", "d8", "go"])
    proc2, req2 = _run_cli(tmp_path, ["dossier", "list-skills", "d8"])

    assert proc1.returncode == 0
    assert proc2.returncode == 0
    assert req1 == [
        {
            "method": "POST",
            "url": "http://localhost:8000/dossier/add-skill",
            "json": {"dossier_id": "d8", "skill": "go"},
        }
    ]
    assert req2 == [
        {
            "method": "GET",
            "url": "http://localhost:8000/dossier/skills/d8",
            "json": None,
        }
    ]


def test_list_projects(tmp_path: Path):
    proc, requests = _run_cli(tmp_path, ["dossier", "list-projects", "d9"])

    assert proc.returncode == 0
    assert json.loads(proc.stdout) == {"dossier_id": "d9", "projects": ["p1"]}
    assert requests == [
        {
            "method": "GET",
            "url": "http://localhost:8000/dossier/projects/d9",
            "json": None,
        }
    ]


def test_list_reflections(tmp_path: Path):
    proc, requests = _run_cli(tmp_path, ["dossier", "list-reflections", "d10"])

    assert proc.returncode == 0
    assert json.loads(proc.stdout) == {"dossier_id": "d10", "reflections": ["r1"]}
    assert requests == [
        {
            "method": "GET",
            "url": "http://localhost:8000/dossier/reflections/d10",
            "json": None,
        }
    ]
