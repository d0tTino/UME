import sys

# ruff: noqa: E402

import importlib.util
from pathlib import Path
import types
import pytest

root = Path(__file__).resolve().parents[1]
package = types.ModuleType("ume")
package.__path__ = [str(root / "src" / "ume")]
sys.modules["ume"] = package
package.VectorStore = object  # type: ignore[attr-defined]
package.create_vector_store = lambda *_, **__: None

# Provide minimal FastAPI stubs so ume.api can be imported without the real
# dependency installed.
fastapi_mod = types.ModuleType("fastapi")

class _FastAPI:
    def __init__(self, *_: object, **__: object) -> None:
        self.state = types.SimpleNamespace()

    def on_event(self, *_: object, **__: object):  # pragma: no cover - stub
        def _wrap(func):
            return func

        return _wrap

    def middleware(self, *_: object, **__: object):  # pragma: no cover - stub
        def _wrap(func):
            return func

        return _wrap

    def include_router(self, *_: object, **__: object) -> None:  # pragma: no cover - stub
        return None

    def exception_handler(self, *_: object, **__: object):  # pragma: no cover - stub
        def _wrap(func):
            return func

        return _wrap


fastapi_mod.FastAPI = _FastAPI  # type: ignore[attr-defined]
fastapi_mod.Request = object  # type: ignore[attr-defined]
responses_mod = types.ModuleType("fastapi.responses")
responses_mod.JSONResponse = object  # type: ignore[attr-defined]
responses_mod.Response = object  # type: ignore[attr-defined]
exceptions_mod = types.ModuleType("fastapi.exceptions")
exceptions_mod.RequestValidationError = Exception  # type: ignore[attr-defined]
sys.modules.setdefault("fastapi", fastapi_mod)
sys.modules.setdefault("fastapi.responses", responses_mod)
sys.modules.setdefault("fastapi.exceptions", exceptions_mod)

api_deps_stub = types.ModuleType("ume.api_deps")
api_deps_stub.POLICY_DIR = root
api_deps_stub.TOKENS = {}
api_deps_stub.configure_graph = lambda *_: None
api_deps_stub.configure_vector_store = lambda *_: None
api_deps_stub.remove_expired_tokens = lambda: None
sys.modules.setdefault("ume.api_deps", api_deps_stub)

empty_router = types.SimpleNamespace()
for _mod in [
    "graph_routes",
    "vector_routes",
    "policy_routes",
    "auth_routes",
    "metrics_routes",
    "dashboard_routes",
    "pii_routes",
    "recommendations_routes",
    "feedback_routes",
    "snapshot_routes",
    "ledger_routes",
]:
    m = types.ModuleType(f"ume.{_mod}")
    m.router = empty_router
    sys.modules.setdefault(f"ume.{_mod}", m)

from ume.event_ledger import EventLedger
from ume import retention

# Patch FastAPILimiter to avoid optional dependency requirement
class _DummyLimiter:
    async def __call__(self, *args, **kwargs):
        return None

    @classmethod
    async def init(cls, *args, **kwargs):
        return None

sys.modules["fastapi_limiter"] = type("m", (), {"FastAPILimiter": _DummyLimiter})
sys.modules.setdefault(
    "fastapi_limiter.depends",
    type(
        "m",
        (),
        {
            "RateLimiter": type(
                "RateLimiter",
                (),
                {
                    "__init__": lambda self, *_, **__: None,
                    "__call__": lambda self, *_, **__: None,
                },
            )
        },
    ),
)
sys.modules.setdefault("sse_starlette", type("m", (), {}))
sys.modules.setdefault(
    "sse_starlette.sse",
    type("m", (), {"EventSourceResponse": object}),
)
grpc_util = type("m", (), {"first_version_is_lower": lambda *_: False})
sys.modules["grpc._utilities"] = grpc_util
grpc_mod = type("m", (), {"__version__": "1.74.0"})
sys.modules["grpc"] = grpc_mod
sys.modules.setdefault("google", type("m", (), {}))

spec_api = importlib.util.spec_from_file_location("ume.api", root / "src" / "ume" / "api.py")
assert spec_api and spec_api.loader
api = importlib.util.module_from_spec(spec_api)
sys.modules["ume.api"] = api
spec_api.loader.exec_module(api)


@pytest.mark.asyncio
async def test_api_compaction_thread_stops(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    ledger = EventLedger(str(tmp_path / "ledger.db"))
    monkeypatch.setattr(sys.modules["ume.event_ledger"], "event_ledger", ledger)
    monkeypatch.setattr(api.settings, "UME_LEDGER_COMPACTION_INTERVAL", 0.01, raising=False)

    await api._start_token_cleanup()
    thread = retention._ledger_thread
    assert thread is not None and thread.is_alive()

    await api._stop_token_cleanup()
    assert api._ledger_compaction_stop is None
    assert thread.is_alive() is False
    retention.stop_ledger_compaction_scheduler()
    ledger.close()
