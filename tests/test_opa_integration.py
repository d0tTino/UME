import pytest
from types import SimpleNamespace

from ume.event import Event, EventType
from ume.plugins.alignment.rego_engine import RegoPolicyEngine, PolicyViolationError  # type: ignore[attr-defined]
from ume.policy.opa_client import OPAClient

httpx = pytest.importorskip("httpx")


def test_opa_client_query() -> None:
    client = OPAClient(base_url="http://opa")
    calls: list[dict[str, object]] = []

    def fake_post(url: str, json: dict[str, object], headers: dict[str, str]) -> SimpleNamespace:
        calls.append({"url": url, "json": json, "headers": headers})
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"result": True},
        )

    client._client.post = fake_post  # type: ignore[method-assign]
    result = client.query("ume/allow", {"foo": "bar"})
    assert result is True
    assert calls[0]["url"] == "http://opa/v1/data/ume/allow"


def test_rego_engine_delegates_to_opa() -> None:
    engine = RegoPolicyEngine(policy_paths=None, opa_client=OPAClient(base_url="http://opa"))
    event = Event(
        event_type=EventType.CREATE_NODE,
        timestamp=0,
        payload={"node_id": "n1", "attributes": {}},
    )
    captured: dict[str, object] = {}

    def fake_query(path: str, input_data: dict[str, object]) -> bool:
        captured["path"] = path
        captured["input"] = input_data
        return True

    engine._opa_client.query = fake_query  # type: ignore[method-assign]
    engine.validate(event)
    payload = captured["input"]
    assert captured["path"] == "ume/allow"
    assert payload["event"]["event_type"] == EventType.CREATE_NODE
    assert payload["graph"] == {}


def test_rego_engine_opa_denied() -> None:
    engine = RegoPolicyEngine(policy_paths=None, opa_client=OPAClient(base_url="http://opa"))
    event = Event(
        event_type=EventType.CREATE_NODE,
        timestamp=0,
        payload={"node_id": "n1", "attributes": {}},
    )
    engine._opa_client.query = lambda *_args, **_kwargs: False  # type: ignore[method-assign]
    with pytest.raises(PolicyViolationError):
        engine.validate(event)
