#!/usr/bin/env python3
# ruff: noqa: E402
import argparse
import logging
import os
import sys
import warnings
from pathlib import Path
import json
import httpx

# Ensure local package import when run directly without installation
_src_path = Path(__file__).resolve().parent / "src"
if _src_path.exists() and str(_src_path) not in sys.path:
    sys.path.insert(0, str(_src_path))

from ume.logging_utils import configure_logging
from ume.config import settings
import ume
from ume.cli.compose import (
    _compose_down,
    _compose_ps,
    _quickstart,
)

quickstart = _quickstart
from ume.cli.prompt import UMEPrompt, create_graph_adapter

# Detect if a lightweight stub was injected for testing.
_UME_STUB = not hasattr(ume, "__file__")


def _cleanup_stub() -> None:
    """Remove temporary ``ume`` stubs injected by tests."""
    if _UME_STUB:
        for mod in ["ume", "ume.benchmarks", "ume.federation", "ume.auto_snapshot"]:
            sys.modules.pop(mod, None)


def _snapshot_schedule(interval: int) -> None:
    """Run periodic snapshotting until interrupted."""
    from ume.auto_snapshot import enable_periodic_snapshot, disable_periodic_snapshot

    graph = create_graph_adapter(settings.UME_CLI_DB, role=None)
    thread, stop = enable_periodic_snapshot(
        graph, settings.UME_SNAPSHOT_PATH, interval
    )
    print(
        f"Snapshots will be written to {settings.UME_SNAPSHOT_PATH} every {interval} seconds."
    )
    print("Press Ctrl+C to stop.")
    try:
        while thread.is_alive():
            thread.join(timeout=1)
    except KeyboardInterrupt:
        pass
    finally:
        stop()
        disable_periodic_snapshot()
        print("Snapshot scheduler stopped.")


def _dossier_view(dossier_id: str) -> None:
    """Fetch and display dossier details from the running API."""
    base_url = "http://localhost:8000"
    headers = {}
    if settings.UME_API_TOKEN:
        headers["Authorization"] = f"Bearer {settings.UME_API_TOKEN}"
    try:
        resp = httpx.get(f"{base_url}/dossier/{dossier_id}", headers=headers, timeout=5)
        resp.raise_for_status()
        print(json.dumps(resp.json(), indent=2))
    except httpx.HTTPError as exc:
        print(f"Request failed: {exc}")


def _dossier_add_project(dossier_id: str, project_id: str) -> None:
    """Send a request to add a project to a dossier."""
    base_url = "http://localhost:8000"
    headers = {}
    if settings.UME_API_TOKEN:
        headers["Authorization"] = f"Bearer {settings.UME_API_TOKEN}"
    payload = {"dossier_id": dossier_id, "project_id": project_id}
    try:
        resp = httpx.post(f"{base_url}/dossier/add-project", json=payload, headers=headers, timeout=5)
        resp.raise_for_status()
        print(json.dumps(resp.json(), indent=2))
    except httpx.HTTPError as exc:
        print(f"Request failed: {exc}")


def main() -> None:
    """Entry point for the ``ume-cli`` console script."""
    parser = argparse.ArgumentParser(description="UME CLI")
    parser.add_argument(
        "--show-warnings",
        action="store_true",
        help="Display Python warnings during CLI execution",
    )
    parser.add_argument(
        "--warnings-log",
        metavar="PATH",
        help="File to log warnings even when they are not displayed",
    )

    sub = parser.add_subparsers(dest="command")
    up_parser = sub.add_parser(
        "up", help="Create .env, generate certs and start the stack"
    )
    sub.add_parser("down", help="Stop Docker Compose stack")
    quick_parser = sub.add_parser(
        "quickstart",
        help="Create .env, generate certs and start the stack (same as 'up')",
    )
    sub.add_parser("ps", help="Show status and health of Docker Compose services")
    snap_parser = sub.add_parser(
        "snapshot-schedule",
        help="Periodically snapshot the graph",
    )
    snap_parser.add_argument("--interval", type=int, default=60)

    dossier_parser = sub.add_parser("dossier", help="Manage dossiers")
    dossier_sub = dossier_parser.add_subparsers(dest="dossier_cmd")
    view_p = dossier_sub.add_parser("view", help="View a dossier")
    view_p.add_argument("dossier_id")
    add_p = dossier_sub.add_parser("add-project", help="Add a project to a dossier")
    add_p.add_argument("dossier_id")
    add_p.add_argument("project_id")
    for p in (up_parser, quick_parser):
        p.add_argument(
            "--no-confirm",
            action="store_true",
            help="Create .env and certs without prompting",
        )
        p.add_argument(
            "--force-build",
            action="store_true",
            help="Reinstall and rebuild frontend assets",
        )

    args = parser.parse_args()

    try:
        if args.command in {"up", "quickstart"}:
            _quickstart(
                getattr(args, "no_confirm", False),
                getattr(args, "force_build", False),
            )
            return
        if args.command == "down":
            _compose_down()
            return
        if args.command == "ps":
            _compose_ps()
            return
        if args.command == "snapshot-schedule":
            _snapshot_schedule(args.interval)
            return
        if args.command == "dossier":
            if args.dossier_cmd == "view":
                _dossier_view(args.dossier_id)
            elif args.dossier_cmd == "add-project":
                _dossier_add_project(args.dossier_id, args.project_id)
            return

        configure_logging()

        _setup_warnings(args.show_warnings, args.warnings_log)

        UMEPrompt().cmdloop()
    finally:
        _cleanup_stub()

def _setup_warnings(display: bool, log_file: str | None) -> None:
    """Configure how Python warnings are handled."""
    warnings.simplefilter("default")

    logger = None
    if log_file:
        dir_path = os.path.dirname(log_file)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)
        logger = logging.getLogger("ume_cli.warnings")
        handler = logging.FileHandler(log_file)
        logger.addHandler(handler)
        logger.propagate = False
        logger.setLevel(logging.WARNING)

    orig_showwarning = warnings.showwarning

    def custom_showwarning(
        message: str | Warning,
        category: type[Warning],
        filename: str,
        lineno: int,
        file=None,
        line: str | None = None,
    ) -> None:
        if display:
            orig_showwarning(message, category, filename, lineno, file, line)
        if logger:
            logger.warning(
                "%s:%s: %s: %s", filename, lineno, category.__name__, message
            )

    warnings.showwarning = custom_showwarning


__all__ = ["quickstart", "main"]


if __name__ == "__main__":
    main()
