import pytest
import httpx
from ume.policy import PolicyAPI

respx = pytest.importorskip("respx")


def test_save_and_edit_policy() -> None:
    with respx.mock(assert_all_called=True) as mock:
        save_route = mock.post("http://ume/policies/p.rego").mock(return_value=httpx.Response(200))
        edit_route = mock.put("http://ume/policies/p.rego").mock(return_value=httpx.Response(200))
        api = PolicyAPI(base_url="http://ume", api_key="t")
        api.save_policy("p.rego", "allow = true")
        api.edit_policy("p.rego", "allow = false")
        assert save_route.called
        assert edit_route.called

