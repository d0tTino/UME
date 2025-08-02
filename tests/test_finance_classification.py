import httpx
import pytest

from ume.event import Event
from ume.classification.service import classify_event

respx = pytest.importorskip("respx")


def make_event() -> Event:
    return Event(event_type="CREATE_NODE", timestamp=0, payload={"transaction": {"amount": 1}})


def test_classify_event_finance_categories() -> None:
    with respx.mock(assert_all_called=True) as mock:
        mock.post("http://finance-engine:8000/categorize").mock(
            return_value=httpx.Response(200, json={"categories": ["Food", "Rent"]})
        )
        results = classify_event(make_event())
        assert [r.tag for r in results] == ["finance:food", "finance:rent"]


def test_classify_event_finance_error() -> None:
    with respx.mock(assert_all_called=True) as mock:
        mock.post("http://finance-engine:8000/categorize").mock(
            side_effect=httpx.ConnectError("boom")
        )
        results = classify_event(make_event())
        assert results == []
