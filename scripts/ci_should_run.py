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
    """Return True if every file is Markdown, reStructuredText, plaintext, or
    lives under ``docs/``.
    """

    doc_exts = (
        ".md",
        ".rst",
        ".txt",
        ".mdx",
        ".adoc",
    )
    for path in files:
        if path.startswith("docs/"):
            continue
        if any(path.endswith(ext) for ext in doc_exts):
            continue
        return False
    return True


def code_diff_present(diff_lines: list[str]) -> bool:
    """Return True if any added/removed line contains real code.

    The function walks through ``diff_lines`` and keeps track of whether the
    current position is inside a triple-quoted block. All lines within such a
    block are treated as documentation/comment changes.
    """

    in_triple = False
    for line in diff_lines:
        if line.startswith("+++ ") or line.startswith("--- "):
            continue
        if line.startswith("@@"):
            in_triple = False
            continue

        prefix = line[:1]
        if prefix not in {"+", "-", " "}:
            continue

        content = line[1:]
        stripped = content.strip()

        quote_count = stripped.count('"""') + stripped.count("'''")
        if quote_count:
            if quote_count % 2 == 1:
                in_triple = not in_triple
            cleaned = stripped.replace('"""', "").replace("'''", "").strip()
            if not cleaned or in_triple:
                continue

        if prefix == " ":
            # Context line outside a quoted block
            continue

        if in_triple:
            continue
        if not stripped:
            continue
        if stripped.startswith("#") or stripped.startswith("//"):
            continue

        return True

    return False


def main() -> int:
    base = run(["git", "merge-base", "HEAD", "origin/main"])[0]
    changed_files = run(["git", "diff", "--name-only", base, "HEAD"])

    if docs_only(changed_files):
        return 1

    diff_lines = run(["git", "diff", "-U1", base, "HEAD"])
    return 0 if code_diff_present(diff_lines) else 1


if __name__ == "__main__":
    sys.exit(main())
