import importlib
import sys
import types
from unittest.mock import MagicMock
import pytest


def _setup_pinecone(monkeypatch: 'pytest.MonkeyPatch'):
    index_mock = MagicMock()
    pinecone_mod = types.ModuleType("pinecone")
    pinecone_mod.init = MagicMock()
    pinecone_mod.Index = lambda name: index_mock
    monkeypatch.setitem(sys.modules, "pinecone", pinecone_mod)
    return index_mock


def test_pinecone_backend_registration(monkeypatch):
    _setup_pinecone(monkeypatch)
    sys.modules.pop("ume.vector_backends.pinecone", None)
    sys.modules.pop("ume.vector_backends", None)
    vb = importlib.import_module("ume.vector_backends")
    assert "pinecone" in vb.available_backends()
    assert vb.get_backend("pinecone") is vb.PineconeBackend


def test_pinecone_backend_add_query(monkeypatch):
    index_mock = _setup_pinecone(monkeypatch)
    sys.modules.pop("ume.vector_backends.pinecone", None)
    pb = importlib.import_module("ume.vector_backends.pinecone")
    backend = pb.PineconeBackend(
        dim=2, api_key="key", environment="env", index_name="idx"
    )
    index_mock.query.return_value = {"matches": [{"id": "a"}]}

    backend.add("a", [0.1, 0.2])
    index_mock.upsert.assert_called_once_with([("a", [0.1, 0.2])])

    result = backend.query([0.1, 0.2], k=1)
    index_mock.query.assert_called_once_with(vector=[0.1, 0.2], top_k=1)
    assert result == ["a"]
