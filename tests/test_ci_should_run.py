import scripts.ci_should_run as csr


def test_docs_only():
    assert csr.docs_only(["README.md", "docs/intro.rst"]) is True
    assert csr.docs_only(["README.md", "src/foo.py"]) is False

    for ext in (".json", ".toml", ".ini", ".cfg"):
        fname = f"config{ext}"
        assert csr.docs_only([fname]) is True


def test_code_diff_present():
    diff = [
        "@@ -1 +1 @@",
        "-# old comment",
        "+# new comment",
    ]
    assert csr.code_diff_present(diff) is False

    diff2 = ["+print('hi')"]
    assert csr.code_diff_present(diff2) is True
