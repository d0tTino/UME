from . import graph_v1_pb2, graph_v2_pb2

PROTO_MAP = {
    "1.0.0": graph_v1_pb2,
    "2.0.0": graph_v2_pb2,
}

__all__ = ["PROTO_MAP"]
