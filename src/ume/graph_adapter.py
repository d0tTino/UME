"""Compatibility facade for kernel graph adapter contracts."""

from .kernel.graph_adapter import AsyncAdapterMixin, IGraphAdapter

__all__ = ["IGraphAdapter", "AsyncAdapterMixin"]
