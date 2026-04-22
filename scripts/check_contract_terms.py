#!/usr/bin/env python3
"""Fail when deprecated contract terminology is not explicitly marked legacy."""

from __future__ import annotations

from pathlib import Path
import re
import sys

DOC_FILES = [
    Path("README.md"),
    Path("docs/API_REFERENCE.md"),
    Path("docs/ARCHITECTURE_OVERVIEW.md"),
]

DEPRECATED_CONTRACT_PATTERNS = [
    r"\bflat external producer contract\b",
    r"\bevent envelope contract\b",
    r"\bsnake_case ingest fields\b",
    r"\bhistorical transport shape(s)?\b",
]


def _is_heading(line: str) -> bool:
    return line.lstrip().startswith("#")


def _has_legacy_label(line: str) -> bool:
    return re.search(r"\blegacy(?:\b|[_-])", line, flags=re.IGNORECASE) is not None


def check_file(path: Path) -> list[str]:
    failures: list[str] = []
    active_heading = ""
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if _is_heading(line):
            active_heading = line
        for pattern in DEPRECATED_CONTRACT_PATTERNS:
            if re.search(pattern, line, flags=re.IGNORECASE):
                if _has_legacy_label(line) or _has_legacy_label(active_heading):
                    continue
                failures.append(
                    f"{path}:{lineno}: deprecated contract term '{pattern}' must include an explicit legacy label (line or active heading)."
                )
    return failures


def main() -> int:
    failures: list[str] = []
    for path in DOC_FILES:
        if not path.exists():
            failures.append(f"{path}: missing expected documentation file")
            continue
        failures.extend(check_file(path))

    if failures:
        print("Contract terminology check failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("Contract terminology check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
