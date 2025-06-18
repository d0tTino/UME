"""Backward compatibility wrapper for :mod:`ume.pipeline.stream_processor`."""
import importlib
import sys

module = importlib.import_module("ume.pipeline.stream_processor")
sys.modules[__name__] = module
