import importlib.util
from pathlib import Path
import sys

module_path = Path(__file__).resolve().parents[1] / "src" / "ume" / "tokenization.py"
spec = importlib.util.spec_from_file_location("ume.tokenization", module_path)
assert spec and spec.loader
tokenization = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = tokenization
spec.loader.exec_module(tokenization)

def test_tokenize_without_tiktoken(monkeypatch):
    monkeypatch.setattr(tokenization, "_tiktoken", None, raising=False)
    assert tokenization.tokenize("Foo bar") == ["Foo", "bar"]

def test_tokenize_with_tiktoken(monkeypatch):
    calls = {}

    class FakeEncoding:
        def encode(self, text):
            calls["encode"] = text
            return [1, 2]

        def decode(self, ids):
            return {1: "foo", 2: "bar"}[ids[0]]

    class FakeTiktoken:
        def get_encoding(self, name):
            calls["get_encoding"] = name
            return FakeEncoding()

    monkeypatch.setattr(tokenization, "_tiktoken", FakeTiktoken(), raising=False)
    tokens = tokenization.tokenize("hello")
    assert tokens == ["foo", "bar"]
    assert calls == {"get_encoding": "cl100k_base", "encode": "hello"}
