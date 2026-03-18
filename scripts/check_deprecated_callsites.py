"""Fail CI when deprecated shim callsites are introduced outside allowlisted files."""

from __future__ import annotations

from pathlib import Path
import re

REPO_ROOT = Path(__file__).resolve().parents[1]
TARGET_DIRS = ("src", "tests")

DEPRECATED_TOP_LEVEL_EXPORTS = {
    "MockGraph",
    "PersistentGraph",
    "RoleBasedGraphAdapter",
    "AccessDeniedError",
    "PermissionsGraphAdapter",
    "PolicyViolationError",
    "apply_event_to_graph",
    "ProcessingError",
    "snapshot_graph_to_file",
    "load_graph_from_file",
    "SnapshotError",
    "DEFAULT_SCHEMA_MANAGER",
    "get_audit_entries",
    "Task",
    "DAGExecutor",
    "Neo4jGraph",
    "VectorBackend",
    "VectorStore",
    "VectorStoreListener",
    "create_default_store",
    "FaissBackend",
    "ChromaBackend",
    "generate_embedding",
    "OntologyListener",
    "configure_ontology_graph",
}

LEGACY_TOP_LEVEL_ALLOWLIST = {
    "tests/test_alignment_plugins.py",
    "tests/test_analytics.py",
    "tests/test_api.py",
    "tests/test_api_events.py",
    "tests/test_api_mutations.py",
    "tests/test_api_rbac.py",
    "tests/test_api_redact_endpoints.py",
    "tests/test_api_snapshot.py",
    "tests/test_audit_logging.py",
    "tests/test_auto_snapshot.py",
    "tests/test_calendar_decision_api.py",
    "tests/test_calendar_event_rollback.py",
    "tests/test_calendar_event_validation.py",
    "tests/test_calendar_invites.py",
    "tests/test_calendar_layer_routes.py",
    "tests/test_dag_executor.py",
    "tests/test_decision_group.py",
    "tests/test_decisions_routes.py",
    "tests/test_financial_account_routes.py",
    "tests/test_dossier_telemetry_rbac.py",
    "tests/test_graph_consumer.py",
    "tests/test_graph_retention.py",
    "tests/test_graph_serialization.py",
    "tests/test_graphql.py",
    "tests/test_graphql_advanced.py",
    "tests/test_import_safety.py",
    "tests/test_listeners.py",
    "tests/test_live_integrations.py",
    "tests/test_llm_ferry.py",
    "tests/test_mixed_access_api.py",
    "tests/test_ontology.py",
    "tests/test_permissioned_client_flows.py",
    "tests/test_permissions_adapter.py",
    "tests/test_permissions_routes.py",
    "tests/test_processing.py",
    "tests/test_projection_engine_event_types.py",
    "tests/test_projection_worker.py",
    "tests/test_query_helpers.py",
    "tests/test_rbac_adapter.py",
    "tests/test_schema_versioning.py",
    "tests/test_snapshot_roundtrip.py",
    "tests/test_sse.py",
    "tests/test_traversal_methods.py",
    "tests/test_users_routes.py",
    "tests/test_vector_api.py",
    "tests/test_vector_store.py",
    "tests/test_deprecated_callsites.py",
    "src/ume_client/ume_pb2.py",
    "src/ume/proto/ume_pb2.py",
}

TOP_LEVEL_IMPORT_PATTERN = re.compile(
    r"from\s+ume\s+import\s+(?P<imports>[^\n]+)|(?P<module>\bume\.(?P<attr>{attrs})\b)|getattr\(\s*ume\s*,\s*['\"](?P<getattr>{attrs})['\"]".format(
        attrs="|".join(sorted(DEPRECATED_TOP_LEVEL_EXPORTS))
    )
)

PATTERNS: dict[str, tuple[re.Pattern[str], set[str]]] = {
    "ume.services.mutate.run_mutation": (
        re.compile(r"\brun_mutation\("),
        {"src/ume/services/mutate.py"},
    ),
    "ume.services.mutate.run_mutation_async": (
        re.compile(r"\brun_mutation_async\("),
        {"src/ume/services/mutate.py"},
    ),
    "ume.stream_processor": (
        re.compile(r"(?:from\s+ume\s+import\s+stream_processor|(?:from|import)\s+ume\.stream_processor\b)"),
        {"src/ume/stream_processor.py"},
    ),
}


def _iter_python_files(root: Path):
    for dirname in TARGET_DIRS:
        base = root / dirname
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            yield path


def _top_level_export_violations(text: str, rel_path: str) -> list[str]:
    if rel_path in LEGACY_TOP_LEVEL_ALLOWLIST:
        return []

    violations: list[str] = []
    for match in TOP_LEVEL_IMPORT_PATTERN.finditer(text):
        imports = match.group("imports")
        names: set[str] = set()
        if imports:
            for part in imports.split(","):
                candidate = part.strip().split(" as ", 1)[0].strip()
                if candidate in DEPRECATED_TOP_LEVEL_EXPORTS:
                    names.add(candidate)
        else:
            candidate = match.group("attr") or match.group("getattr")
            if candidate:
                names.add(candidate)

        if not names:
            continue

        line = text.count("\n", 0, match.start()) + 1
        for name in sorted(names):
            violations.append(f"{rel_path}:{line}: deprecated callsite for ume.{name}")
    return violations


def find_violations(root: Path = REPO_ROOT) -> list[str]:
    violations: list[str] = []
    for path in _iter_python_files(root):
        rel_path = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        violations.extend(_top_level_export_violations(text, rel_path))
        for key, (pattern, allowlist) in PATTERNS.items():
            if rel_path in allowlist:
                continue
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                violations.append(f"{rel_path}:{line}: deprecated callsite for {key}")
    return violations


def main() -> int:
    violations = find_violations()
    if violations:
        print("Deprecated callsite check failed:")
        for violation in violations:
            print(f" - {violation}")
        return 1
    print("Deprecated callsite check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
