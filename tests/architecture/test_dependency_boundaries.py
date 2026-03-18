from scripts.lint_dependencies import lint_kernel_dependencies


def test_kernel_only_depends_on_kernel_or_external_modules() -> None:
    violations = lint_kernel_dependencies()
    assert not violations, "\n".join(violations)
