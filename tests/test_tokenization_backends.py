from pathlib import Path
import importlib.util
import sys


def _load_tokenization(monkeypatch, tiktoken_module: object | None):
    module_path = Path(__file__).resolve().parents[1] / "src" / "ume" / "tokenization.py"
    spec = importlib.util.spec_from_file_location("ume.tokenization", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    if tiktoken_module is not None:
        monkeypatch.setitem(sys.modules, "tiktoken", tiktoken_module)
    else:
        sys.modules.pop("tiktoken", None)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return module


def test_tokenize_fallback(monkeypatch):
    mod = _load_tokenization(monkeypatch, None)
    assert mod.tokenize("foo bar") == ["foo", "bar"]


def test_tokenize_with_tiktoken(monkeypatch):
    class FakeEncoding:
        def encode(self, text: str):
            assert text == "hello"
            return [1, 2]

        def decode(self, ids):
            return {1: "h", 2: "i"}[ids[0]]

    class FakeTiktoken:
        def get_encoding(self, name: str):
            assert name == "cl100k_base"
            return FakeEncoding()

    mod = _load_tokenization(monkeypatch, FakeTiktoken())
    assert mod.tokenize("hello") == ["h", "i"]
