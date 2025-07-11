#!/usr/bin/env python3
"""Determine whether CI should run for the current diff.

Exit status ``0`` indicates code changes requiring tests and linting. A status
of ``1`` means only documentation files or comment lines were modified, so CI
can be safely skipped.
"""

from __future__ import annotations

import subprocess
import sys
import importlib.util


EXTRA_MODULES = {
    "vector": "faiss",
    "embedding": "sentence_transformers",
    "grpc_server": "grpc",
}


def run(cmd: list[str]) -> list[str]:
    """Run a command and return the output split into lines."""

    return subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode().splitlines()


def find_base_commit() -> str:
    """Return the merge base with ``origin/main`` or a fallback commit.

    This helper prevents failures when the remote ``origin`` or its ``main``
    branch is not available by falling back to ``HEAD^`` or the repository's
    first commit.
    """

    try:
        return run(["git", "merge-base", "HEAD", "origin/main"])[0]
    except subprocess.CalledProcessError:
        pass

    for ref in ["HEAD^", "HEAD~1"]:
        try:
            return run(["git", "rev-parse", ref])[0]
        except subprocess.CalledProcessError:
            continue

    return run(["git", "rev-list", "--max-parents=0", "HEAD"])[0]


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


def missing_extras() -> list[str]:
    """Return extras that are not currently installed."""

    missing: list[str] = []
    for extra, module in EXTRA_MODULES.items():
        if importlib.util.find_spec(module) is None:
            missing.append(extra)
    return missing


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
    base = find_base_commit()
    changed_files = run(["git", "diff", "--name-only", base, "HEAD"])

    if docs_only(changed_files):
        return 1

    diff_lines = run(["git", "diff", "-U1", base, "HEAD"])
    should_run = code_diff_present(diff_lines)
    if should_run:
        missing = missing_extras()
        if missing:
            hint = ", ".join(f"[{name}]" for name in missing)
            print(f"Hint: install extras {hint} to enable all tests.", file=sys.stderr)
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
