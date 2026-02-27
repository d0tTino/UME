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
from ume.bootstrap.runtime import bootstrap_runtime
from ume.cli.compose import (
    _compose_down,
    _compose_ps,
    _quickstart,
)

quickstart = _quickstart
from ume.cli.prompt import UMEPrompt, create_graph_adapter


def _ledger_replay(end_offset: int | None, end_timestamp: int | None) -> None:
    """Print a graph snapshot reconstructed from the event ledger."""

    from ume.replay import snapshot_from_event_ledger

    snapshot = snapshot_from_event_ledger(
        end_offset=end_offset, end_timestamp=end_timestamp
    )
    print(json.dumps(snapshot, indent=2))


def _replay_graph(db_path: str | None, end_offset: int | None) -> None:
    """Rebuild a graph from the event ledger and print a summary."""

    from ume.replay import graph_from_event_ledger

    graph = graph_from_event_ledger(db_path=db_path, end_offset=end_offset)
    node_count = len(graph.get_all_node_ids())
    edge_count = len(graph.get_all_edges())
    location = f" at {db_path}" if db_path and db_path != ":memory:" else ""
    print(f"Rebuilt graph{location} with {node_count} nodes and {edge_count} edges")


def _list_plugins(capability: str | None = None) -> None:
    """Print plugin registrations with constructor metadata."""
    from ume.plugins.registry import list_plugins

    plugins = list_plugins(capability=capability)
    payload = []
    for item in plugins:
        metadata = item["metadata"]
        payload.append(
            {
                "capability": item["capability"],
                "name": item["name"],
                "metadata": {
                    "source": metadata.source,
                    "entry_point_group": metadata.entry_point_group,
                    "module_path": metadata.module_path,
                    "lazy": metadata.lazy,
                    "details": metadata.details,
                },
            }
        )
    print(json.dumps(payload, indent=2))

# Detect if a lightweight stub was injected for testing.
_UME_STUB = not hasattr(ume, "__file__")

if not _UME_STUB:
    bootstrap_runtime("ume")


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


def _dossier_snapshot_schedule(interval: int) -> None:
    """Run periodic dossier snapshotting until interrupted."""
    from ume.dossier import Dossier
    from ume.dossier.scheduler import (
        start_dossier_snapshot_scheduler,
        stop_dossier_snapshot_scheduler,
    )

    dossier = Dossier.load()
    thread, stop = start_dossier_snapshot_scheduler(dossier, interval_seconds=interval)
    history = dossier.root / "history"
    print(
        f"Snapshots will be written to {history} every {interval} seconds."
    )
    print("Press Ctrl+C to stop.")
    try:
        while thread.is_alive():
            thread.join(timeout=1)
    except KeyboardInterrupt:
        pass
    finally:
        stop()
        stop_dossier_snapshot_scheduler()
        print("Dossier snapshot scheduler stopped.")


def _dossier_init(dossier_id: str) -> None:
    """Initialize a dossier directory for ``dossier_id``."""
    from ume.dossier import Dossier

    base = Path(os.environ.get("UME_DOSSIER_PATH", "~/.ume_dossier")).expanduser()
    path = base / dossier_id
    dossier = Dossier.init_dossier(path)
    print(f"Dossier '{dossier_id}' initialized at {dossier.root}")


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


def _dossier_add_reflection(
    dossier_id: str, text: str, attachments: list[str] | None = None
) -> None:
    """Send a request to append a reflection."""
    base_url = "http://localhost:8000"
    headers = {}
    if settings.UME_API_TOKEN:
        headers["Authorization"] = f"Bearer {settings.UME_API_TOKEN}"
    payload = {"dossier_id": dossier_id, "text": text}
    if attachments:
        payload["attachments"] = attachments
    try:
        resp = httpx.post(
            f"{base_url}/dossier/add-reflection",
            json=payload,
            headers=headers,
            timeout=5,
        )
        resp.raise_for_status()
        print(json.dumps(resp.json(), indent=2))
    except httpx.HTTPError as exc:
        print(f"Request failed: {exc}")


def _dossier_set_pref(dossier_id: str, key: str, value: str) -> None:
    """Send a request to update a preference key."""
    base_url = "http://localhost:8000"
    headers = {}
    if settings.UME_API_TOKEN:
        headers["Authorization"] = f"Bearer {settings.UME_API_TOKEN}"
    payload = {"dossier_id": dossier_id, "key": key, "value": value}
    try:
        resp = httpx.post(
            f"{base_url}/dossier/set-pref",
            json=payload,
            headers=headers,
            timeout=5,
        )
        resp.raise_for_status()
        print(json.dumps(resp.json(), indent=2))
    except httpx.HTTPError as exc:
        print(f"Request failed: {exc}")


def _dossier_set_shareable(dossier_id: str, **flags: str) -> None:
    """Send a request to update shareable flags."""
    base_url = "http://localhost:8000"
    headers = {}
    if settings.UME_API_TOKEN:
        headers["Authorization"] = f"Bearer {settings.UME_API_TOKEN}"
    payload: dict[str, object] = {"dossier_id": dossier_id}
    payload.update(flags)
    try:
        resp = httpx.post(
            f"{base_url}/dossier/set-shareable",
            json=payload,
            headers=headers,
            timeout=5,
        )
        resp.raise_for_status()
        print(json.dumps(resp.json(), indent=2))
    except httpx.HTTPError as exc:
        print(f"Request failed: {exc}")


def _dossier_add_value(dossier_id: str, value: str) -> None:
    """Send a request to append a value."""
    base_url = "http://localhost:8000"
    headers = {}
    if settings.UME_API_TOKEN:
        headers["Authorization"] = f"Bearer {settings.UME_API_TOKEN}"
    payload = {"dossier_id": dossier_id, "value": value}
    try:
        resp = httpx.post(
            f"{base_url}/dossier/add-value",
            json=payload,
            headers=headers,
            timeout=5,
        )
        resp.raise_for_status()
        print(json.dumps(resp.json(), indent=2))
    except httpx.HTTPError as exc:
        print(f"Request failed: {exc}")


def _dossier_add_skill(dossier_id: str, skill: str) -> None:
    """Send a request to append a skill."""
    base_url = "http://localhost:8000"
    headers = {}
    if settings.UME_API_TOKEN:
        headers["Authorization"] = f"Bearer {settings.UME_API_TOKEN}"
    payload = {"dossier_id": dossier_id, "skill": skill}
    try:
        resp = httpx.post(
            f"{base_url}/dossier/add-skill",
            json=payload,
            headers=headers,
            timeout=5,
        )
        resp.raise_for_status()
        print(json.dumps(resp.json(), indent=2))
    except httpx.HTTPError as exc:
        print(f"Request failed: {exc}")


def _dossier_add_goal(dossier_id: str, goal: str) -> None:
    """Send a request to append a goal."""
    base_url = "http://localhost:8000"
    headers = {}
    if settings.UME_API_TOKEN:
        headers["Authorization"] = f"Bearer {settings.UME_API_TOKEN}"
    payload = {"dossier_id": dossier_id, "goal": goal}
    try:
        resp = httpx.post(
            f"{base_url}/dossier/add-goal",
            json=payload,
            headers=headers,
            timeout=5,
        )
        resp.raise_for_status()
        print(json.dumps(resp.json(), indent=2))
    except httpx.HTTPError as exc:
        print(f"Request failed: {exc}")


def _dossier_list_skills(dossier_id: str) -> None:
    """Fetch and print the skill list."""
    base_url = "http://localhost:8000"
    headers = {}
    if settings.UME_API_TOKEN:
        headers["Authorization"] = f"Bearer {settings.UME_API_TOKEN}"
    try:
        resp = httpx.get(
            f"{base_url}/dossier/skills/{dossier_id}",
            headers=headers,
            timeout=5,
        )
        resp.raise_for_status()
        print(json.dumps(resp.json(), indent=2))
    except httpx.HTTPError as exc:
        print(f"Request failed: {exc}")


def _dossier_list_goals(dossier_id: str) -> None:
    """Fetch and print the goal list."""
    base_url = "http://localhost:8000"
    headers = {}
    if settings.UME_API_TOKEN:
        headers["Authorization"] = f"Bearer {settings.UME_API_TOKEN}"
    try:
        resp = httpx.get(
            f"{base_url}/dossier/goals/{dossier_id}",
            headers=headers,
            timeout=5,
        )
        resp.raise_for_status()
        print(json.dumps(resp.json(), indent=2))
    except httpx.HTTPError as exc:
        print(f"Request failed: {exc}")


def _dossier_list_values(dossier_id: str) -> None:
    """Fetch and print the value list."""
    base_url = "http://localhost:8000"
    headers = {}
    if settings.UME_API_TOKEN:
        headers["Authorization"] = f"Bearer {settings.UME_API_TOKEN}"
    try:
        resp = httpx.get(
            f"{base_url}/dossier/values/{dossier_id}",
            headers=headers,
            timeout=5,
        )
        resp.raise_for_status()
        print(json.dumps(resp.json(), indent=2))
    except httpx.HTTPError as exc:
        print(f"Request failed: {exc}")


def _dossier_list_projects(dossier_id: str) -> None:
    """Fetch and print the project list."""
    base_url = "http://localhost:8000"
    headers = {}
    if settings.UME_API_TOKEN:
        headers["Authorization"] = f"Bearer {settings.UME_API_TOKEN}"
    try:
        resp = httpx.get(
            f"{base_url}/dossier/projects/{dossier_id}",
            headers=headers,
            timeout=5,
        )
        resp.raise_for_status()
        print(json.dumps(resp.json(), indent=2))
    except httpx.HTTPError as exc:
        print(f"Request failed: {exc}")


def _dossier_list_reflections(dossier_id: str) -> None:
    """Fetch and print the reflection list."""
    base_url = "http://localhost:8000"
    headers = {}
    if settings.UME_API_TOKEN:
        headers["Authorization"] = f"Bearer {settings.UME_API_TOKEN}"
    try:
        resp = httpx.get(
            f"{base_url}/dossier/reflections/{dossier_id}",
            headers=headers,
            timeout=5,
        )
        resp.raise_for_status()
        print(json.dumps(resp.json(), indent=2))
    except httpx.HTTPError as exc:
        print(f"Request failed: {exc}")


def _dossier_add_memory(
    dossier_id: str, text: str, attachments: list[str] | None = None
) -> None:
    """Send a request to append a memory entry."""
    base_url = "http://localhost:8000"
    headers = {}
    if settings.UME_API_TOKEN:
        headers["Authorization"] = f"Bearer {settings.UME_API_TOKEN}"
    payload = {"dossier_id": dossier_id, "text": text}
    if attachments:
        payload["attachments"] = attachments
    try:
        resp = httpx.post(
            f"{base_url}/dossier/add-memory",
            json=payload,
            headers=headers,
            timeout=5,
        )
        resp.raise_for_status()
        print(json.dumps(resp.json(), indent=2))
    except httpx.HTTPError as exc:
        print(f"Request failed: {exc}")


def _dossier_list_memories(dossier_id: str) -> None:
    """Fetch and print the memory list."""
    base_url = "http://localhost:8000"
    headers = {}
    if settings.UME_API_TOKEN:
        headers["Authorization"] = f"Bearer {settings.UME_API_TOKEN}"
    try:
        resp = httpx.get(
            f"{base_url}/dossier/memories/{dossier_id}",
            headers=headers,
            timeout=5,
        )
        resp.raise_for_status()
        print(json.dumps(resp.json(), indent=2))
    except httpx.HTTPError as exc:
        print(f"Request failed: {exc}")


def _dossier_snapshot(dossier_id: str) -> None:
    """Request a dossier snapshot from the API."""
    base_url = "http://localhost:8000"
    headers = {}
    if settings.UME_API_TOKEN:
        headers["Authorization"] = f"Bearer {settings.UME_API_TOKEN}"
    payload = {"dossier_id": dossier_id}
    try:
        resp = httpx.post(
            f"{base_url}/dossier/snapshot",
            json=payload,
            headers=headers,
            timeout=5,
        )
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

    replay_parser = sub.add_parser(
        "ledger-replay", help="Output a snapshot built from the ledger"
    )
    replay_parser.add_argument("--end-offset", type=int)
    replay_parser.add_argument("--end-timestamp", type=int)

    replay_graph_parser = sub.add_parser(
        "replay-graph",
        help="Rebuild a graph from the event ledger",
    )
    replay_graph_parser.add_argument("--db-path", default=":memory:")
    replay_graph_parser.add_argument("--end-offset", type=int)

    plugins_parser = sub.add_parser("plugins", help="List registered plugins")
    plugins_parser.add_argument(
        "--capability",
        help="Filter by capability (graph_backend, integration_adapter, vector_backend)",
    )

    dossier_parser = sub.add_parser("dossier", help="Manage dossiers")
    dossier_sub = dossier_parser.add_subparsers(dest="dossier_cmd")
    view_p = dossier_sub.add_parser("view", help="View a dossier")
    view_p.add_argument("dossier_id")
    add_p = dossier_sub.add_parser("add-project", help="Add a project to a dossier")
    add_p.add_argument("dossier_id")
    add_p.add_argument("project_id")
    refl_p = dossier_sub.add_parser("add-reflection", help="Add a reflection entry")
    refl_p.add_argument("dossier_id")
    refl_p.add_argument("text")
    refl_p.add_argument(
        "--attach",
        action="append",
        default=[],
        help="Attachment for the reflection (repeatable)",
    )
    mem_p = dossier_sub.add_parser("add-memory", help="Add a knowledge entry")
    mem_p.add_argument("dossier_id")
    mem_p.add_argument("text")
    mem_p.add_argument(
        "--attach",
        action="append",
        default=[],
        help="Attachment for the memory (repeatable)",
    )
    init_p = dossier_sub.add_parser("init", help="Initialize a new dossier")
    init_p.add_argument("dossier_id")
    pref_p = dossier_sub.add_parser("set-pref", help="Set a preference key")
    pref_p.add_argument("dossier_id")
    pref_p.add_argument("key")
    pref_p.add_argument("value")
    share_p = dossier_sub.add_parser("set-shareable", help="Update shareable flags")
    share_p.add_argument("dossier_id")
    share_p.add_argument("--shareable", choices=["true", "false"])
    share_p.add_argument("--projects", dest="shareable_projects", choices=["true", "false"])
    share_p.add_argument("--reflections", dest="shareable_reflections", choices=["true", "false"])
    share_p.add_argument("--skills", dest="shareable_skills", choices=["true", "false"])
    share_p.add_argument("--values", dest="shareable_values", choices=["true", "false"])
    share_p.add_argument("--memories", dest="shareable_memories", choices=["true", "false"])
    val_p = dossier_sub.add_parser("add-value", help="Add a value entry")
    val_p.add_argument("dossier_id")
    val_p.add_argument("value")
    skill_p = dossier_sub.add_parser("add-skill", help="Add a skill entry")
    skill_p.add_argument("dossier_id")
    skill_p.add_argument("skill")
    goal_p = dossier_sub.add_parser("add-goal", help="Add a goal entry")
    goal_p.add_argument("dossier_id")
    goal_p.add_argument("goal")
    list_proj_p = dossier_sub.add_parser(
        "list-projects", help="List projects"
    )
    list_proj_p.add_argument("dossier_id")
    list_refl_p = dossier_sub.add_parser(
        "list-reflections", help="List reflections"
    )
    list_refl_p.add_argument("dossier_id")
    list_mem_p = dossier_sub.add_parser("list-memories", help="List knowledge entries")
    list_mem_p.add_argument("dossier_id")
    list_skills_p = dossier_sub.add_parser("list-skills", help="List skills")
    list_skills_p.add_argument("dossier_id")
    list_values_p = dossier_sub.add_parser("list-values", help="List values")
    list_values_p.add_argument("dossier_id")
    list_goals_p = dossier_sub.add_parser("list-goals", help="List goals")
    list_goals_p.add_argument("dossier_id")
    snap_p = dossier_sub.add_parser("snapshot", help="Snapshot dossier")
    snap_p.add_argument("dossier_id")
    sched_p = dossier_sub.add_parser(
        "snapshot-schedule", help="Periodically snapshot dossier"
    )
    sched_p.add_argument("--interval", type=int, default=60)
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
        if args.command == "ledger-replay":
            _ledger_replay(args.end_offset, args.end_timestamp)
            return
        if args.command == "replay-graph":
            _replay_graph(args.db_path, args.end_offset)
            return
        if args.command == "plugins":
            _list_plugins(args.capability)
            return
        if args.command == "dossier":
            if args.dossier_cmd == "view":
                _dossier_view(args.dossier_id)
            elif args.dossier_cmd == "init":
                _dossier_init(args.dossier_id)
            elif args.dossier_cmd == "add-project":
                _dossier_add_project(args.dossier_id, args.project_id)
            elif args.dossier_cmd == "add-reflection":
                _dossier_add_reflection(args.dossier_id, args.text, args.attach)
            elif args.dossier_cmd == "add-memory":
                _dossier_add_memory(args.dossier_id, args.text, args.attach)
            elif args.dossier_cmd == "set-pref":
                _dossier_set_pref(args.dossier_id, args.key, args.value)
            elif args.dossier_cmd == "set-shareable":
                flags = {}
                for name in [
                    "shareable",
                    "shareable_projects",
                    "shareable_reflections",
                    "shareable_skills",
                    "shareable_values",
                    "shareable_memories",
                ]:
                    val = getattr(args, name)
                    if val is not None:
                        flags[name] = val == "true"
                _dossier_set_shareable(args.dossier_id, **flags)
            elif args.dossier_cmd == "add-value":
                _dossier_add_value(args.dossier_id, args.value)
            elif args.dossier_cmd == "add-skill":
                _dossier_add_skill(args.dossier_id, args.skill)
            elif args.dossier_cmd == "add-goal":
                _dossier_add_goal(args.dossier_id, args.goal)
            elif args.dossier_cmd == "list-memories":
                _dossier_list_memories(args.dossier_id)
            elif args.dossier_cmd == "list-skills":
                _dossier_list_skills(args.dossier_id)
            elif args.dossier_cmd == "list-values":
                _dossier_list_values(args.dossier_id)
            elif args.dossier_cmd == "list-goals":
                _dossier_list_goals(args.dossier_id)
            elif args.dossier_cmd == "list-projects":
                _dossier_list_projects(args.dossier_id)
            elif args.dossier_cmd == "list-reflections":
                _dossier_list_reflections(args.dossier_id)
            elif args.dossier_cmd == "snapshot":
                _dossier_snapshot(args.dossier_id)
            elif args.dossier_cmd == "snapshot-schedule":
                _dossier_snapshot_schedule(args.interval)
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
