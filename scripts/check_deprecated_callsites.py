"""Fail CI when deprecated shim callsites are introduced outside allowlisted files."""

from __future__ import annotations

from pathlib import Path
import re

REPO_ROOT = Path(__file__).resolve().parents[1]
TARGET_DIRS = ("src", "tests")

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


def find_violations(root: Path = REPO_ROOT) -> list[str]:
    violations: list[str] = []
    for path in _iter_python_files(root):
        rel_path = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
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
