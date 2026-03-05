#!/usr/bin/env python3
"""Fail when deprecated architecture terms appear in core documentation."""

from __future__ import annotations

from pathlib import Path
import re
import sys

DOC_FILES = [
    Path("README.md"),
    Path("QUICKSTART.md"),
    Path("docs/API_REFERENCE.md"),
    Path("docs/ARCHITECTURE_OVERVIEW.md"),
]

# term -> replacement guidance
DEPRECATED_PATTERNS: dict[str, str] = {
    r"\bUME_GRAPH_ADAPTER\b": "Use UME_GRAPH_BACKEND",
    r"\bget_adapter\b": "Use create_graph_adapter",
    r"\badapter map\b": "Use graph backend plugin registry terminology",
    r"\bvector adapter\b": "Use vector backend terminology",
}


def find_matches(path: Path) -> list[str]:
    matches: list[str] = []
    text = path.read_text(encoding="utf-8")
    in_concept_mapping = False
    for lineno, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if (
            stripped.lower().startswith("#")
            and "concept mapping (legacy -> current)" in stripped.lower()
        ):
            in_concept_mapping = True
            continue
        if (
            in_concept_mapping
            and stripped.startswith("#")
            and "concept mapping (legacy -> current)" not in stripped.lower()
        ):
            in_concept_mapping = False

        for pattern, guidance in DEPRECATED_PATTERNS.items():
            if re.search(pattern, line):
                if in_concept_mapping and line.lstrip().startswith("|"):
                    continue
                matches.append(
                    f"{path}:{lineno}: found deprecated term matching /{pattern}/. {guidance}."
                )
    return matches


def main() -> int:
    failures: list[str] = []
    for path in DOC_FILES:
        if not path.exists():
            failures.append(f"{path}: missing expected core doc file")
            continue
        failures.extend(find_matches(path))

    if failures:
        print("Deprecated architecture terminology detected:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("Architecture terminology check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
