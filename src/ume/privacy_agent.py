"""Backward compatibility wrapper for :mod:`ume.pipeline.privacy_agent`."""
import importlib
import sys

module = importlib.import_module("ume.pipeline.privacy_agent")
sys.modules[__name__] = module
