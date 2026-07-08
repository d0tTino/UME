#!/usr/bin/env python3
"""Fail when legacy architecture terms or doc contract violations appear."""

from __future__ import annotations

from pathlib import Path
import re
import sys

CORE_DOC_FILES = [
    Path("README.md"),
    Path("docs/API_REFERENCE.md"),
    Path("docs/ARCHITECTURE_OVERVIEW.md"),
    Path("docs/GRAPH_MODEL.md"),
    Path("docs/INTEGRATIONS.md"),
]

BACKLINK_REQUIRED_DOCS = [
    Path("docs/API_REFERENCE.md"),
    Path("docs/INTEGRATIONS.md"),
]

ARCHITECTURE_DOCS_REQUIRING_GLOSSARY = [
    Path("README.md"),
    Path("docs/ARCHITECTURE_OVERVIEW.md"),
    Path("docs/API_REFERENCE.md"),
    Path("docs/INTEGRATIONS.md"),
]

# term -> replacement guidance
DEPRECATED_PATTERNS: dict[str, str] = {
    r"\bUME_GRAPH_ADAPTER\b": "Use UME_GRAPH_BACKEND",
    r"\badapter map\b": "Use graph backend plugin registry terminology",
    r"\bvector adapter\b": "Use vector backend terminology",
    r"\bUME_VECTOR_ADAPTER\b": "Use UME_VECTOR_BACKEND",
    r"\bcanonical envelope\b": "Use canonical event terminology",
}

CONTRACT_DOC_FILES = [Path("docs/API_REFERENCE.md")]
CONTRACT_FIELD_PATTERNS: dict[str, str] = {
    r"`event_type`|\bevent_type\b": (
        "Use producer-facing eventType except in canonical parser or legacy migration sections"
    ),
    r"`event_id`|\bevent_id\b": (
        "Use producer-facing eventId except in canonical parser or legacy migration sections"
    ),
    r"`schema_version`|\bschema_version\b": (
        "Use producer-facing schemaVersion except in canonical parser, "
        "version policy, or legacy migration sections"
    ),
    r"`producer_signature`|\bproducer_signature\b": (
        "Use producer-facing signature except in canonical parser or legacy migration sections"
    ),
    r"`correlation_id`|\bcorrelation_id\b": (
        "Use producer-facing correlationId except in canonical parser or legacy migration sections"
    ),
    r"`subject_entity`|\bsubject_entity\b": (
        "Use producer-facing subjectEntity except in canonical parser or legacy migration sections"
    ),
}

CONTRACT_ALLOWED_HEADING_TOKENS = (
    "legacy migration",
    "historical inputs",
    "canonical parser",
    "producer migration matrix",
    "parse_event error examples",
    "event contract version policy",
)

CANONICAL_LINK = "ARCHITECTURE_OVERVIEW.md"
GLOSSARY_LINK = "GLOSSARY.md"
LEGACY_HEADING_TOKEN = "legacy migration"


def _is_legacy_section_heading(line: str) -> bool:
    stripped = line.strip().lower()
    return stripped.startswith("#") and LEGACY_HEADING_TOKEN in stripped


def _is_contract_allowed_section_heading(line: str) -> bool:
    stripped = line.strip().lower()
    return stripped.startswith("#") and any(
        token in stripped for token in CONTRACT_ALLOWED_HEADING_TOKENS
    )


def _is_heading(line: str) -> bool:
    return line.strip().startswith("#")


def find_term_matches(path: Path) -> list[str]:
    matches: list[str] = []
    text = path.read_text(encoding="utf-8")
    in_approved_section = False
    for lineno, line in enumerate(text.splitlines(), start=1):
        if _is_legacy_section_heading(line) or _is_contract_allowed_section_heading(line):
            in_approved_section = True
            continue
        if in_approved_section and _is_heading(line):
            in_approved_section = False

        for pattern, guidance in DEPRECATED_PATTERNS.items():
            if re.search(pattern, line):
                if in_approved_section or "metadata.schema_version" in line:
                    continue
                matches.append(
                    f"{path}:{lineno}: found deprecated term matching /{pattern}/ "
                    "outside an approved legacy/canonical contract section. "
                    f"{guidance}."
                )
    return matches


def find_contract_field_matches(path: Path) -> list[str]:
    matches: list[str] = []
    text = path.read_text(encoding="utf-8")
    in_approved_section = False
    for lineno, line in enumerate(text.splitlines(), start=1):
        if _is_contract_allowed_section_heading(line):
            in_approved_section = True
            continue
        if in_approved_section and _is_heading(line):
            in_approved_section = False

        for pattern, guidance in CONTRACT_FIELD_PATTERNS.items():
            if re.search(pattern, line):
                if in_approved_section or "metadata.schema_version" in line:
                    continue
                matches.append(
                    f"{path}:{lineno}: found deprecated producer contract field "
                    f"matching /{pattern}/ outside an approved legacy/canonical "
                    f"contract section. {guidance}."
                )
    return matches

def check_module_doc_backlinks() -> list[str]:
    failures: list[str] = []
    for path in BACKLINK_REQUIRED_DOCS:
        text = path.read_text(encoding="utf-8")
        first_lines = "\n".join(text.splitlines()[:12])
        if CANONICAL_LINK not in first_lines:
            failures.append(
                f"{path}: missing canonical backlink to {CANONICAL_LINK} in top-of-file preface"
            )
    return failures


def check_glossary_links() -> list[str]:
    failures: list[str] = []
    for path in ARCHITECTURE_DOCS_REQUIRING_GLOSSARY:
        text = path.read_text(encoding="utf-8")
        if GLOSSARY_LINK not in text:
            failures.append(f"{path}: missing glossary reference to {GLOSSARY_LINK}")
    return failures


def main() -> int:
    failures: list[str] = []

    for path in CORE_DOC_FILES:
        if not path.exists():
            failures.append(f"{path}: missing expected core doc file")
            continue
        failures.extend(find_term_matches(path))

    for path in CONTRACT_DOC_FILES:
        if not path.exists():
            failures.append(f"{path}: missing expected contract doc file")
            continue
        failures.extend(find_contract_field_matches(path))

    failures.extend(check_module_doc_backlinks())
    failures.extend(check_glossary_links())

    if failures:
        print("Architecture documentation consistency check failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("Architecture documentation consistency check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
