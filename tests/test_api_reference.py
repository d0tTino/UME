import os
import re
import sys
from pathlib import Path
# ruff: noqa: E402

os.environ.setdefault("UME_AUDIT_SIGNING_KEY", "test-key")

class _DummyLimiter:
    async def __call__(self, *_: object, **__: object) -> None:
        return None

    @classmethod
    async def init(cls, *_: object, **__: object) -> None:
        return None

sys.modules.setdefault("fastapi_limiter", type("m", (), {"FastAPILimiter": _DummyLimiter}))

class _RateLimiter:
    def __init__(self, *_: object, **__: object) -> None:
        pass

    async def __call__(self, *_: object, **__: object) -> None:
        return None

sys.modules.setdefault("fastapi_limiter.depends", type("m", (), {"RateLimiter": _RateLimiter}))
neo4j_stub = sys.modules.setdefault("neo4j", type("m", (), {}))
setattr(neo4j_stub, "GraphDatabase", type("GraphDatabase", (), {}))
setattr(neo4j_stub, "Driver", type("Driver", (), {}))

from ume.api import app


def _normalize(path: str) -> str:
    """Replace path parameter names with generic placeholders."""
    return re.sub(r"\{[^}]+\}", "{}", path)


def test_documented_routes_exist() -> None:
    text = Path("docs/API_REFERENCE.md").read_text()
    pattern = re.compile(r"^###\s+([A-Z]+)\s+`([^`]+)`", re.MULTILINE)
    documented = {(m, _normalize(p)) for m, p in pattern.findall(text)}

    actual = {
        (m, _normalize(route.path))
        for route in app.router.routes
        for m in route.methods
        if m in {"GET", "POST", "DELETE", "PATCH", "PUT"}
    }

    missing = documented - actual
    assert not missing, f"Routes documented but missing in app: {missing}"
