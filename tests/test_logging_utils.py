import logging
from unittest.mock import patch
import importlib.util
from pathlib import Path
import sys

import structlog

module_path = Path(__file__).resolve().parents[1] / "src" / "ume" / "logging_utils.py"
spec = importlib.util.spec_from_file_location("ume.logging_utils", module_path)
assert spec and spec.loader
logging_utils = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = logging_utils
spec.loader.exec_module(logging_utils)
configure_logging = logging_utils.configure_logging


def test_configure_logging_json_and_console():
    with patch("structlog.configure") as conf, patch("logging.basicConfig") as basic:
        configure_logging(level="WARNING", json_logs=False)
        procs = conf.call_args.kwargs["processors"]
        assert isinstance(procs[-1], structlog.dev.ConsoleRenderer)
        basic.assert_called_once_with(level=logging.WARNING, format="%(message)s")

    with patch("structlog.configure") as conf, patch("logging.basicConfig"):
        configure_logging(level="INFO", json_logs=True)
        procs = conf.call_args.kwargs["processors"]
        assert isinstance(procs[-1], structlog.processors.JSONRenderer)

