#!/usr/bin/env python3
"""Determine whether CI should run for the current diff.

Exit status ``0`` indicates code changes requiring tests and linting. A status
of ``1`` means only documentation files or comment lines were modified, so CI
can be safely skipped.
"""

from __future__ import annotations

import subprocess
import sys


def run(cmd: list[str]) -> list[str]:
    """Run a command and return the output split into lines."""

    return subprocess.check_output(cmd).decode().splitlines()


def docs_only(files: list[str]) -> bool:
    """Return True if every file is a documentation file."""

    doc_exts = (".md", ".rst", ".txt", ".yml", ".yaml")
    for path in files:
        if path.startswith("docs/"):
            continue
        if any(path.endswith(ext) for ext in doc_exts):
            continue
        return False
    return True


def code_diff_present(diff_lines: list[str]) -> bool:
    """Return True if any added/removed line contains real code."""

    for line in diff_lines:
        if line.startswith("+++ ") or line.startswith("--- "):
            continue
        if line.startswith("@@"):
            continue
        if line.startswith("+") or line.startswith("-"):
            content = line[1:].strip()
            if not content:
                continue
            if content.startswith("#"):
                continue
            if content.startswith("//"):
                continue
            stripped = content.lstrip()
            if stripped.startswith('"""') or stripped.startswith("'''"):
                continue
            return True
    return False


def main() -> int:
    base = run(["git", "merge-base", "HEAD", "origin/main"])[0]
    changed_files = run(["git", "diff", "--name-only", base, "HEAD"])

    if docs_only(changed_files):
        return 1

    diff_lines = run(["git", "diff", "-U0", base, "HEAD"])
    return 0 if code_diff_present(diff_lines) else 1


if __name__ == "__main__":
    sys.exit(main())
