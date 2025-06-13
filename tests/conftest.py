from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure the src directory is importable when UME isn't installed
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ume import privacy_agent as privacy_agent_module


@pytest.fixture
def privacy_agent():
    return privacy_agent_module
