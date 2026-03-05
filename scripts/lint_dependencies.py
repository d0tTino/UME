"""Static dependency linter for architecture boundaries."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KERNEL_DIR = ROOT / "src" / "ume" / "kernel"
DISALLOWED = "ume.domains"


def _module_name(path: Path) -> str:
    rel = path.relative_to(ROOT / "src")
    return ".".join(rel.with_suffix("").parts)


def _is_disallowed_import(node: ast.AST, module_name: str) -> bool:
    if isinstance(node, ast.Import):
        return any(alias.name == DISALLOWED or alias.name.startswith(f"{DISALLOWED}.") for alias in node.names)
    if isinstance(node, ast.ImportFrom):
        if node.level:
            package = module_name.split(".")[:-1]
            base = package[:]
            up = node.level - 1
            if up > len(base):
                resolved = ""
            else:
                resolved = ".".join(base[: len(base) - up])
            if node.module:
                resolved = f"{resolved}.{node.module}" if resolved else node.module
        else:
            resolved = node.module or ""
        return resolved == DISALLOWED or resolved.startswith(f"{DISALLOWED}.")
    return False


def lint_kernel_dependencies() -> list[str]:
    violations: list[str] = []
    for path in sorted(KERNEL_DIR.glob("*.py")):
        if path.name == "__init__.py":
            continue
        module_name = _module_name(path)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if _is_disallowed_import(node, module_name):
                violations.append(f"{path.relative_to(ROOT)} imports {DISALLOWED}")
    return violations


def main() -> int:
    violations = lint_kernel_dependencies()
    if violations:
        print("Kernel dependency violations found:")
        for violation in violations:
            print(f"- {violation}")
        return 1
    print("Kernel dependency lint passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
