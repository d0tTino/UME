"""Deprecated compatibility wrapper for :mod:`ume.pipeline.privacy_agent`."""
from __future__ import annotations

import warnings
from .pipeline.privacy_agent import *  # noqa: F401,F403

warnings.warn(
    "ume.privacy_agent is deprecated; use ume.pipeline.privacy_agent instead.",
    DeprecationWarning,
    stacklevel=2,
)
