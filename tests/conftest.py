import pytest
from ume import privacy_agent as privacy_agent_module


@pytest.fixture
def privacy_agent():
    return privacy_agent_module
