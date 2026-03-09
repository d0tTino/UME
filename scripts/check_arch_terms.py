#!/usr/bin/env python3
"""Fail when legacy architecture terms or doc contract violations appear."""

from __future__ import annotations

from pathlib import Path
import re
import sys

CORE_DOC_FILES = [
    Path("README.md"),
    Path("QUICKSTART.md"),
    Path("docs/API_REFERENCE.md"),
    Path("docs/ARCHITECTURE_OVERVIEW.md"),
    Path("docs/INTEGRATIONS.md"),
]

DOC_MODULE_FILES = sorted(
    path for path in Path("docs").glob("*.md") if path.name != "ARCHITECTURE_OVERVIEW.md"
)

# term -> replacement guidance
DEPRECATED_PATTERNS: dict[str, str] = {
    r"\bUME_GRAPH_ADAPTER\b": "Use UME_GRAPH_BACKEND",
    r"\badapter map\b": "Use graph backend plugin registry terminology",
    r"\bvector adapter\b": "Use vector backend terminology",
    r"\bUME_VECTOR_ADAPTER\b": "Use UME_VECTOR_BACKEND",
    r"\bcanonical envelope\b": "Use canonical event terminology",
}

CANONICAL_LINK = "ARCHITECTURE_OVERVIEW.md"



def _is_in_allowed_legacy_mapping(line: str, in_concept_mapping: bool) -> bool:
    return in_concept_mapping and line.lstrip().startswith("|")


def find_term_matches(path: Path) -> list[str]:
    matches: list[str] = []
    text = path.read_text(encoding="utf-8")
    in_concept_mapping = False
    for lineno, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if stripped.lower().startswith("#") and "concept mapping (legacy -> current)" in stripped.lower():
            in_concept_mapping = True
            continue
        if in_concept_mapping and stripped.startswith("#") and "concept mapping (legacy -> current)" not in stripped.lower():
            in_concept_mapping = False

        for pattern, guidance in DEPRECATED_PATTERNS.items():
            if re.search(pattern, line):
                if _is_in_allowed_legacy_mapping(line, in_concept_mapping):
                    continue
                matches.append(
                    f"{path}:{lineno}: found deprecated term matching /{pattern}/. {guidance}."
                )
    return matches


def check_module_doc_backlinks() -> list[str]:
    failures: list[str] = []
    for path in DOC_MODULE_FILES:
        text = path.read_text(encoding="utf-8")
        first_lines = "\n".join(text.splitlines()[:12])
        if CANONICAL_LINK not in first_lines:
            failures.append(
                f"{path}: missing canonical backlink to {CANONICAL_LINK} in top-of-file preface"
            )
    return failures


def main() -> int:
    failures: list[str] = []

    for path in CORE_DOC_FILES:
        if not path.exists():
            failures.append(f"{path}: missing expected core doc file")
            continue
        failures.extend(find_term_matches(path))

    failures.extend(check_module_doc_backlinks())

    if failures:
        print("Architecture documentation consistency check failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("Architecture documentation consistency check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
