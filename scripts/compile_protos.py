#!/usr/bin/env python
"""Compile protobuf definitions for UME."""
from pathlib import Path
import subprocess
import sys
from pkg_resources import resource_filename

BASE_DIR = Path(__file__).resolve().parent.parent
# Proto definitions live under a single directory at the repository root.
PROTO_DIR = BASE_DIR / "protos"
OUT_DIR = BASE_DIR / "src" / "ume" / "proto"
CLIENT_OUT_DIR = BASE_DIR / "src" / "ume_client"

def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    proto_files = [str(p) for p in PROTO_DIR.glob("*.proto")]

    if not proto_files:
        print("No proto files found", file=sys.stderr)
        sys.exit(1)

    grpc_include = resource_filename("grpc_tools", "_proto")

    cmd = [
        "protoc",
        f"--proto_path={PROTO_DIR}",
        f"--proto_path={grpc_include}",
        f"--python_out={OUT_DIR}",
    ] + proto_files

    subprocess.check_call(cmd)

    # Keep client stubs in sync with server-side definitions
    CLIENT_OUT_DIR.mkdir(parents=True, exist_ok=True)
    for generated in OUT_DIR.glob("*_pb2.py"):
        target = CLIENT_OUT_DIR / generated.name
        target.write_bytes(generated.read_bytes())


if __name__ == "__main__":
    main()
