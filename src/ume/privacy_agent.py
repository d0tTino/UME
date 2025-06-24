"""Deprecated compatibility wrapper for :mod:`ume.pipeline.privacy_agent`."""
from __future__ import annotations

import warnings
from .pipeline.privacy_agent import *  # noqa: F401,F403
from .pipeline import privacy_agent as _pa

_ANALYZER = _pa._ANALYZER
_ANONYMIZER = _pa._ANONYMIZER

warnings.warn(
    "ume.privacy_agent is deprecated; use ume.pipeline.privacy_agent instead.",
    DeprecationWarning,
    stacklevel=2,
)
