from ume.domains.classification import apply_classification
from ume.domains.extensions import run_domain_extensions
from ume.event import Event
from ume.kernel.policy import PolicyContext


def _context() -> PolicyContext:
    event = Event(
        event_type="entity.created",
        timestamp=0,
        payload={"attributes": {"text": "pii email@example.com"}},
    )
    return PolicyContext(
        source="test",
        raw_payload=None,
        transport_data={},
        canonical_event={"event_type": event.event_type, "payload": event.payload},
        original_event=event,
        effective_event=event,
    )


def test_domain_extension_runner_merges_details() -> None:
    context = _context()

    def extension(_: PolicyContext) -> dict[str, int]:
        return {"x": 1}

    details = run_domain_extensions(context, [extension])

    assert details == {"x": 1}


def test_classification_extension_is_invokable_from_domain_pack() -> None:
    context = _context()
    details = run_domain_extensions(context, [apply_classification])
    assert "classification_count" in details
