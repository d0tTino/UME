from scripts.lint_dependencies import lint_kernel_dependencies


def test_kernel_does_not_depend_on_domains() -> None:
    violations = lint_kernel_dependencies()
    assert not violations, "\n".join(violations)
