"""Fail CI on unplanned schema breakages across contract bundles."""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _required_fields(major: int, schema_name: str) -> set[str]:
    from ume.schemas.contracts import load_bundle_schema

    schema = load_bundle_schema(major, schema_name)
    return set(schema.get("required", []))


def _seed_event(version: str) -> dict[str, object]:
    return {
        "metadata": {
            "event_type": "CREATE_NODE",
            "timestamp": 1,
            "schema_version": version,
            "event_id": "seed",
            "source": "ci",
        },
        "graph": {"node_id": "n1", "target_node_id": None, "label": None},
        "payload": {"node_id": "n1", "attributes": {}},
    }


def _enforce_single_shape_parsing() -> None:
    """Fail if non-legacy ingress code parses both modern + legacy shapes directly."""

    forbidden_needles = (
        'payload.get("event", payload)',
        'payload.get("event")',
        'normalized = dict(deepcopy(payload.get("event", payload)))',
    )
    allowed = {Path("src/ume/events/legacy_transform.py")}
    scan_files = [
        Path("src/ume/event.py"),
        Path("src/ume/events/contract.py"),
        *Path("src/ume/events/adapters").glob("*.py"),
    ]

    violations: list[str] = []
    for rel in scan_files:
        if rel in allowed:
            continue
        content = (ROOT / rel).read_text()
        for needle in forbidden_needles:
            if needle in content:
                violations.append(f"{rel}: contains forbidden dual-shape parser marker {needle!r}")

    if violations:
        raise SystemExit(
            "Direct dual-shape parsing is forbidden outside ume.events.legacy_transform:\n"
            + "\n".join(sorted(violations))
        )


def _check_event_contract_parity() -> None:
    from ume.events.contract_registry import contract_event_types, taxonomy_event_types
    from ume.events.handlers import EVENT_HANDLER_REGISTRY

    schema_event_types = contract_event_types()
    taxonomy_types = taxonomy_event_types()
    parser_types = taxonomy_types
    handler_types = frozenset(
        event_type.value if hasattr(event_type, "value") else str(event_type)
        for event_type in EVENT_HANDLER_REGISTRY
    )

    layers = {
        "schema bundle": schema_event_types,
        "event taxonomy": taxonomy_types,
        "parser": parser_types,
        "handler registry": handler_types,
    }
    universe = set().union(*layers.values())
    problems: list[str] = []
    for layer_name, layer_types in layers.items():
        missing = sorted(universe - layer_types)
        if missing:
            problems.append(f"{layer_name} missing: {', '.join(missing)}")

    if problems:
        raise SystemExit("Event contract parity check failed:\n" + "\n".join(problems))


def main() -> int:
    from ume.events.versioning import downgrade_event, upgrade_event
    from ume.schemas.contracts import supported_contract_majors

    _enforce_single_shape_parsing()
    _check_event_contract_parity()

    majors = list(supported_contract_majors())

    for prev, curr in zip(majors, majors[1:]):
        removed_required = _required_fields(prev, "canonical_event.schema.json") - _required_fields(
            curr, "canonical_event.schema.json"
        )
        if removed_required:
            probe = _seed_event(f"{prev}.0.0")
            upgraded = upgrade_event(probe, f"{curr}.0.0")
            restored = downgrade_event(upgraded, f"{prev}.0.0")
            for field in removed_required:
                if field in {"eventId", "sourceService"}:
                    key = "event_id" if field == "eventId" else "source"
                    if key not in restored.get("metadata", {}):
                        raise SystemExit(
                            f"Breaking field removal '{field}' requires explicit migration transformer ({prev}->{curr})."
                        )

    print("Schema compatibility checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
