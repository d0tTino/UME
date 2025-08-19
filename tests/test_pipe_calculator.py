from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from ume.pipe_calculator import b62_to_int, int_to_b62, evaluate


def run_calc(expr: str) -> str:
    script = Path(__file__).resolve().parents[1] / "src" / "ume" / "pipe_calculator.py"
    result = subprocess.run(
        [sys.executable, str(script)],
        input=expr.encode(),
        capture_output=True,
        check=True,
    )
    return result.stdout.decode().strip()


def test_base62_conversion() -> None:
    value = "Az"
    assert int_to_b62(b62_to_int(value)) == value


def test_addition() -> None:
    assert evaluate(["1", "1", "+"]) == [2]


def test_function_definition() -> None:
    tokens = "fn inc 1 + ; 3 inc".split()
    assert evaluate(tokens) == [4]


def test_cli_usage() -> None:
    output = run_calc("fn inc 1 + ; 3 inc")
    assert output == "4"
