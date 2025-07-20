"""Client bindings for the Universal Memory Engine."""

import sys

from . import events_pb2 as _events_pb2
from . import ume_pb2 as _ume_pb2
from . import ume_pb2_grpc  # after ume_pb2 is registered
from .async_client import AsyncUMEClient

sys.modules.setdefault("events_pb2", _events_pb2)
sys.modules.setdefault("ume_pb2", _ume_pb2)

__all__ = ["ume_pb2", "ume_pb2_grpc", "AsyncUMEClient"]
