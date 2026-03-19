#!/usr/bin/env python
"""Compile protobuf definitions into the canonical UME output directories."""

from __future__ import annotations

import filecmp
import importlib.resources
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
PROTO_DIR = BASE_DIR / "protos"
SERVER_OUT_DIR = BASE_DIR / "src" / "ume" / "proto"
CLIENT_OUT_DIR = BASE_DIR / "src" / "ume_client"
SERVER_SUFFIXES = ("*_pb2.py",)
CLIENT_SUFFIXES = ("*_pb2.py", "*_pb2_grpc.py")


def _proto_files() -> list[Path]:
    proto_files = sorted(PROTO_DIR.glob("*.proto"))
    if not proto_files:
        print("No proto files found", file=sys.stderr)
        sys.exit(1)
    return proto_files


def _run_protoc(server_out_dir: Path, client_out_dir: Path, proto_files: list[Path]) -> None:
    try:
        grpc_include = importlib.resources.files("grpc_tools").joinpath("_proto")
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "grpc_tools is required to compile protobuf client stubs. "
            "Install grpcio-tools in the active environment."
        ) from exc
    base_args = [
        sys.executable,
        "-m",
        "grpc_tools.protoc",
        f"--proto_path={PROTO_DIR}",
        f"--proto_path={grpc_include}",
    ]

    subprocess.check_call(
        base_args
        + [f"--python_out={server_out_dir}"]
        + [str(proto_file) for proto_file in proto_files]
    )
    subprocess.check_call(
        base_args
        + [
            f"--python_out={client_out_dir}",
            f"--grpc_python_out={client_out_dir}",
        ]
        + [str(proto_file) for proto_file in proto_files]
    )


def _sync_generated_files(source_dir: Path, target_dir: Path, suffixes: tuple[str, ...]) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)

    expected_names: set[str] = set()
    for suffix in suffixes:
        for generated in source_dir.glob(suffix):
            expected_names.add(generated.name)
            target = target_dir / generated.name
            if not target.exists() or generated.read_bytes() != target.read_bytes():
                shutil.copy2(generated, target)

    for suffix in suffixes:
        for existing in target_dir.glob(suffix):
            if existing.name not in expected_names:
                existing.unlink()


def _assert_deterministic(proto_files: list[Path]) -> tuple[Path, Path]:
    temp_root = Path(tempfile.mkdtemp(prefix="ume-protos-"))
    first_server = temp_root / "first_server"
    first_client = temp_root / "first_client"
    second_server = temp_root / "second_server"
    second_client = temp_root / "second_client"

    for path in (first_server, first_client, second_server, second_client):
        path.mkdir(parents=True, exist_ok=True)

    _run_protoc(first_server, first_client, proto_files)
    _run_protoc(second_server, second_client, proto_files)

    if not filecmp.dircmp(first_server, second_server).same_files == sorted(
        p.name for p in first_server.iterdir()
    ):
        raise RuntimeError("protobuf Python generation is not deterministic for server outputs")
    if not filecmp.dircmp(first_client, second_client).same_files == sorted(
        p.name for p in first_client.iterdir()
    ):
        raise RuntimeError("protobuf Python generation is not deterministic for client outputs")

    return first_server, first_client


def main() -> None:
    proto_files = _proto_files()
    generated_server_dir, generated_client_dir = _assert_deterministic(proto_files)
    _sync_generated_files(generated_server_dir, SERVER_OUT_DIR, SERVER_SUFFIXES)
    _sync_generated_files(generated_client_dir, CLIENT_OUT_DIR, CLIENT_SUFFIXES)


if __name__ == "__main__":
    main()
