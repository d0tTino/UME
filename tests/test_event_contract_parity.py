from ume.events.contract_registry import contract_event_types, load_event_contracts, taxonomy_event_types
from ume.events.handlers import EVENT_HANDLER_REGISTRY


def test_schema_bundle_covers_event_taxonomy() -> None:
    assert contract_event_types() == taxonomy_event_types()


def test_handler_registry_matches_contract_bundle() -> None:
    handler_types = {event_type.value for event_type in EVENT_HANDLER_REGISTRY}
    assert handler_types == contract_event_types()


def test_contract_payload_constraints_are_derived_from_schema() -> None:
    contracts = load_event_contracts()
    assert contracts["UPDATE_NODE_ATTRIBUTES"].payload_required_fields == {"attributes"}
    assert contracts["CREATE_EDGE"].graph_required_fields == {"node_id", "target_node_id", "label"}
    assert contracts["REDACT_NODE"].graph_required_fields == {"node_id"}
