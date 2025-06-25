import pytest

from ume.event import Event, EventType
from ume.plugins.alignment.rego_engine import RegoPolicyEngine, PolicyViolationError  # type: ignore[attr-defined]
from ume.policy.opa_client import OPAClient

httpx = pytest.importorskip("httpx")
respx = pytest.importorskip("respx")


def test_opa_client_query() -> None:
    client = OPAClient(base_url="http://opa")
    with respx.mock(assert_all_called=True) as mock:
        route = mock.post("http://opa/v1/data/ume/allow").mock(
            return_value=httpx.Response(200, json={"result": True})
        )
        result = client.query("ume/allow", {"foo": "bar"})
        assert route.called
        assert result is True


def test_rego_engine_delegates_to_opa() -> None:
    engine = RegoPolicyEngine(policy_paths=None, opa_client=OPAClient(base_url="http://opa"))
    event = Event(
        event_type=EventType.CREATE_NODE,
        timestamp=0,
        payload={"node_id": "n1", "attributes": {}},
    )
    with respx.mock(assert_all_called=True) as mock:
        mock.post("http://opa/v1/data/ume/allow").mock(
            return_value=httpx.Response(200, json={"result": True})
        )
        engine.validate(event)


def test_rego_engine_opa_denied() -> None:
    engine = RegoPolicyEngine(policy_paths=None, opa_client=OPAClient(base_url="http://opa"))
    event = Event(
        event_type=EventType.CREATE_NODE,
        timestamp=0,
        payload={"node_id": "n1", "attributes": {}},
    )
    with respx.mock(assert_all_called=True) as mock:
        mock.post("http://opa/v1/data/ume/allow").mock(
            return_value=httpx.Response(200, json={"result": False})
        )
        with pytest.raises(PolicyViolationError):
            engine.validate(event)
