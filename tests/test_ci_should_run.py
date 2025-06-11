import scripts.ci_should_run as csr


def test_docs_only():
    assert csr.docs_only(["README.md", "docs/intro.rst"]) is True
    assert csr.docs_only(["README.mdx"]) is True
    assert csr.docs_only(["README.adoc"]) is True
    assert csr.docs_only(["README.md", "src/foo.py"]) is False

    assert csr.docs_only(["config.toml"]) is False


def test_code_diff_present():
    diff = [
        "@@ -1 +1 @@",
        "-# old comment",
        "+# new comment",
    ]
    assert csr.code_diff_present(diff) is False

    diff2 = ["+print('hi')"]
    assert csr.code_diff_present(diff2) is True


def test_docstring_edits_do_not_trigger_ci():
    diff = [
        "@@ -1,6 +1,6 @@",
        " def foo():",
        '-    """Old summary.',
        "-    Old details.",
        '-    """',
        '+    """Old summary.',
        "+    New details.",
        '+    """',
    ]
    assert csr.code_diff_present(diff) is False


def test_nested_triple_quoted_strings():
    diff = [
        "@@ -1,8 +1,8 @@",
        " def foo():",
        '     """Top-level docstring.',
        '-    """inner"""',
        '+    """modified"""',
        '     """',
    ]
    assert csr.code_diff_present(diff) is False


def test_raw_string_with_triple_quotes():
    diff = [
        "@@ -1 +1 @@",
        '-pattern = r"""foo"""',
        '+pattern = r"""bar"""',
    ]
    assert csr.code_diff_present(diff) is True


def test_markdown_code_block_changes_trigger_ci():
    diff = [
        "@@ -1,5 +1,5 @@",
        " ```python",
        '-print("hello")',
        '+print("bye")',
        " ```",
    ]
    assert csr.code_diff_present(diff) is True
