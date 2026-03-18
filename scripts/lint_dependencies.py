"""Static dependency linter for architecture boundaries."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KERNEL_DIR = ROOT / "src" / "ume" / "kernel"
KERNEL_PREFIX = "ume.kernel"


def _module_name(path: Path) -> str:
    rel = path.relative_to(ROOT / "src")
    return ".".join(rel.with_suffix("").parts)


def _resolve_imported_module(node: ast.AST, module_name: str) -> list[str]:
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]

    if isinstance(node, ast.ImportFrom):
        package = module_name.split(".")[:-1]
        if node.level:
            up = node.level - 1
            base = package[: len(package) - up] if up <= len(package) else []
            resolved_base = ".".join(base)
            target = f"{resolved_base}.{node.module}" if node.module and resolved_base else (node.module or resolved_base)
        else:
            target = node.module or ""
        return [target]

    return []


def lint_kernel_dependencies() -> list[str]:
    violations: list[str] = []
    for path in sorted(KERNEL_DIR.glob("*.py")):
        if path.name == "__init__.py":
            continue
        module_name = _module_name(path)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            for imported in _resolve_imported_module(node, module_name):
                if imported.startswith("ume.") and not imported.startswith(f"{KERNEL_PREFIX}."):
                    violations.append(
                        f"{path.relative_to(ROOT)} imports non-kernel module {imported}"
                    )
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
