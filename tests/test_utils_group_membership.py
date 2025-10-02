import pytest
from fastapi import HTTPException

from ume.utils import ensure_group_member


class StubGraph:
    def __init__(self, node):
        self._node = node

    def get_node(self, node_id: str):  # pragma: no cover - simple stub
        return self._node


@pytest.mark.parametrize("group_payload", [None, ["not", "a", "dict"]])
@pytest.mark.parametrize("should_exist", [True, False])
def test_ensure_group_member_missing_group(group_payload, should_exist):
    graph = StubGraph(group_payload)

    with pytest.raises(HTTPException) as exc:
        ensure_group_member(graph, "user", "group", should_exist=should_exist)

    assert exc.value.status_code == 404
    assert exc.value.detail == "Group not found"
