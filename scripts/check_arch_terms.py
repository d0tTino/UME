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
}

ALLOWED_CONTEXT_SNIPPETS = (
    "Concept Mapping (legacy -> current)",
    "| `UME_GRAPH_ADAPTER` | `UME_GRAPH_BACKEND` |",
    "| `get_adapter(...)` | `create_graph_adapter(...)` |",
)


def find_matches(path: Path) -> list[str]:
    matches: list[str] = []
    text = path.read_text(encoding="utf-8")
    for lineno, line in enumerate(text.splitlines(), start=1):
        if any(snippet in line for snippet in ALLOWED_CONTEXT_SNIPPETS):
            continue
        for pattern, guidance in DEPRECATED_PATTERNS.items():
            if re.search(pattern, line):
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
