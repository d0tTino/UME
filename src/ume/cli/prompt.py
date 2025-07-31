from __future__ import annotations
# ruff: noqa: E402

import argparse
import json
import logging
import shlex
import sys
import time
from datetime import datetime, timezone, timedelta
from cmd import Cmd
from pathlib import Path

# Ensure local package import when run directly without installation
_src_path = Path(__file__).resolve().parents[3] / "src"
if _src_path.exists() and str(_src_path) not in sys.path:
    sys.path.insert(0, str(_src_path))

from ume.config import settings
import ume

# Support tests that provide a lightweight ``ume`` stub without all attributes.
parse_event = getattr(ume, "parse_event", lambda *_args, **_kw: None)
apply_event_to_graph = getattr(ume, "apply_event_to_graph", lambda *_args, **_kw: None)
load_graph_into_existing = getattr(ume, "load_graph_into_existing", lambda *_args, **_kw: None)
snapshot_graph_to_file = getattr(ume, "snapshot_graph_to_file", lambda *_args, **_kw: None)
create_graph_adapter = getattr(ume, "create_graph_adapter", lambda *_args, **_kw: None)
RoleBasedGraphAdapter = getattr(ume, "RoleBasedGraphAdapter", object)
enable_snapshot_autosave_and_restore = getattr(
    ume, "enable_snapshot_autosave_and_restore", lambda *_args, **_kw: None
)
ProcessingError = getattr(ume, "ProcessingError", Exception)
EventError = getattr(ume, "EventError", Exception)
SnapshotError = getattr(ume, "SnapshotError", Exception)
IGraphAdapter = getattr(ume, "IGraphAdapter", object)
log_audit_entry = getattr(ume, "log_audit_entry", lambda *_args, **_kw: None)
get_audit_entries = getattr(ume, "get_audit_entries", lambda *_args, **_kw: [])
from ume.benchmarks import benchmark_vector_store

try:  # optional dependency for federation features
    from ume.federation import MirrorMakerDriver
except Exception:  # pragma: no cover - federation optional
    MirrorMakerDriver = None  # type: ignore[misc]
from ume import DEFAULT_SCHEMA_MANAGER


class UMEPrompt(Cmd):
    intro = "Welcome to UME CLI. Type help or ? to list commands.\n"
    prompt = "ume> "

    def __init__(self) -> None:
        super().__init__()
        db_path = settings.UME_CLI_DB
        base_graph = create_graph_adapter(db_path, role=None)
        self.base_graph = base_graph
        role = settings.UME_ROLE
        if role:
            print(f"INFO: UME-CLI running with role: '{role}'")
            graph: IGraphAdapter = RoleBasedGraphAdapter(base_graph, role)
        else:
            print("INFO: UME-CLI running without a specific role (full permissions).")
            graph = base_graph
        self.graph: IGraphAdapter = graph
        if db_path != ":memory:":
            enable_snapshot_autosave_and_restore(
                base_graph, settings.UME_SNAPSHOT_PATH, 24 * 3600
            )
        self.current_timestamp = datetime.now(timezone.utc)
        self.peer_cluster: str | None = None
        self.mm_topics: list[str] = [settings.KAFKA_RAW_EVENTS_TOPIC]
        self.mm_driver: "MirrorMakerDriver | None" = None

    def _log_audit(self, reason: str) -> None:
        user_id = settings.UME_AGENT_ID
        try:
            log_audit_entry(user_id, reason)
        except Exception as e:  # pragma: no cover - logging failure shouldn't crash
            logging.getLogger(__name__).error("Audit log failure: %s", e)

    def _get_timestamp(self) -> str:
        self.current_timestamp += timedelta(seconds=1)
        return self.current_timestamp.isoformat()

    # ----- Node commands -----
    def do_new_node(self, arg: str) -> None:
        """new_node <node_id> <json_attributes>"""
        try:
            parts = shlex.split(arg)
            if len(parts) != 2:
                print("Usage: new_node <node_id> <json_attributes>")
                return
            node_id, json_attrs = parts
            attributes = json.loads(json_attrs)
            event_data = {
                "eventType": "CREATE_NODE",
                "node_id": node_id,
                "payload": {"node_id": node_id, "attributes": attributes},
                "timestamp": self._get_timestamp(),
            }
            evt = parse_event(event_data)
            apply_event_to_graph(evt, self.graph)
            print(f"Node '{node_id}' created.")
        except (json.JSONDecodeError, EventError, ProcessingError) as e:
            print(f"Error: {e}")
            self._log_audit(str(e))
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            self._log_audit(str(e))

    def do_new_edge(self, arg: str) -> None:
        """new_edge <source_id> <target_id> <label>"""
        try:
            parts = shlex.split(arg)
            if len(parts) != 3:
                print("Usage: new_edge <source_id> <target_id> <label>")
                return
            source_id, target_id, label = parts
            event_data = {
                "eventType": "CREATE_EDGE",
                "node_id": source_id,
                "target_node_id": target_id,
                "label": label,
                "timestamp": self._get_timestamp(),
            }
            evt = parse_event(event_data)
            apply_event_to_graph(evt, self.graph)
            print(f"Edge ({source_id})->({target_id}) [{label}] created.")
        except (EventError, ProcessingError) as e:
            print(f"Error: {e}")
            self._log_audit(str(e))
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            self._log_audit(str(e))

    def do_del_edge(self, arg: str) -> None:
        """del_edge <source_id> <target_id> <label>"""
        try:
            parts = shlex.split(arg)
            if len(parts) != 3:
                print("Usage: del_edge <source_id> <target_id> <label>")
                return
            source_id, target_id, label = parts
            event_data = {
                "eventType": "DELETE_EDGE",
                "node_id": source_id,
                "target_node_id": target_id,
                "label": label,
                "timestamp": self._get_timestamp(),
            }
            evt = parse_event(event_data)
            apply_event_to_graph(evt, self.graph)
            print(f"Edge ({source_id})->({target_id}) [{label}] deleted.")
        except (EventError, ProcessingError) as e:
            print(f"Error: {e}")
            self._log_audit(str(e))
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            self._log_audit(str(e))

    def do_redact_node(self, arg: str) -> None:
        node_id = shlex.split(arg)[0] if arg else None
        if not node_id:
            print("Usage: redact_node <node_id>")
            return
        try:
            self.graph.redact_node(node_id)
            print(f"Node '{node_id}' redacted.")
        except ProcessingError as e:
            print(f"Error: {e}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")

    def do_redact_edge(self, arg: str) -> None:
        try:
            parts = shlex.split(arg)
            if len(parts) != 3:
                print("Usage: redact_edge <source_id> <target_id> <label>")
                return
            source_id, target_id, label = parts
            self.graph.redact_edge(source_id, target_id, label)
            print(f"Edge ({source_id})->({target_id}) [{label}] redacted.")
        except ProcessingError as e:
            print(f"Error: {e}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")

    # ----- Query commands -----
    def do_show_nodes(self, arg: str) -> None:
        try:
            nodes = self.graph.get_all_node_ids()
            if not nodes:
                print("No nodes in the graph.")
                return
            print("Nodes:")
            for n in sorted(list(nodes)):
                print(f"  - {n}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")

    def do_show_edges(self, arg: str) -> None:
        try:
            edges = self.graph.get_all_edges()
            if not edges:
                print("No edges in the graph.")
                return
            print("Edges:")
            for src, tgt, lbl in sorted(list(edges)):
                print(f"  - {src} -> {tgt} [{lbl}]")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")

    def do_neighbors(self, arg: str) -> None:
        try:
            parts = shlex.split(arg)
            if not parts:
                print("Usage: neighbors <node_id> [<label>]")
                return
            node_id = parts[0]
            label = parts[1] if len(parts) > 1 else None
            targets = self.graph.find_connected_nodes(node_id, label)
            if not targets:
                print(
                    f"No neighbors found for '{node_id}'"
                    + (f" with label '{label}'." if label else ".")
                )
            else:
                print(
                    f"Neighbors of '{node_id}'"
                    + (f" with label '{label}'" if label else "")
                    + f": {sorted(list(targets))}"
                )
        except ProcessingError as e:
            print(f"Error: {e}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")

    def do_show_audit(self, arg: str) -> None:
        entries = get_audit_entries()
        if not entries:
            print("No audit entries.")
            return
        for e in entries:
            ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(e["timestamp"])) )
            print(f"{ts} | {e.get('user_id')} | {e.get('reason')}")

    # ----- Snapshot commands -----
    def do_snapshot_save(self, arg: str) -> None:
        filepath = shlex.split(arg)[0] if arg else None
        if not filepath:
            print("Usage: snapshot_save <filepath>")
            return
        try:
            snapshot_graph_to_file(self.graph, filepath)
            print(f"Snapshot written to {filepath}")
        except Exception as e:
            print(f"Error saving snapshot: {e}")
            self._log_audit(str(e))

    def do_snapshot_load(self, arg: str) -> None:
        filepath = shlex.split(arg)[0] if arg else None
        if not filepath:
            print("Usage: snapshot_load <filepath>")
            return
        try:
            load_graph_into_existing(self.graph, filepath)
            print(f"Graph restored from {filepath}")
            self._log_audit(f"snapshot loaded from {filepath}")
        except FileNotFoundError:
            print(f"Error: Snapshot file '{filepath}' not found.")
            self._log_audit("snapshot file not found")
        except (json.JSONDecodeError, EventError, ProcessingError, SnapshotError) as e:
            print(f"Error loading snapshot: {e}")
            self._log_audit(str(e))
        except Exception as e:
            print(f"An unexpected error occurred during load: {e}")
            self._log_audit(str(e))

    def do_register_schema(self, arg: str) -> None:
        try:
            version, schema_path, proto_module = shlex.split(arg)
        except ValueError:
            print("Usage: register_schema <version> <schema_path> <proto_module>")
            return
        try:
            DEFAULT_SCHEMA_MANAGER.register_schema(version, schema_path, proto_module)
            print("Schema registered.")
        except Exception as e:
            print(f"Error registering schema: {e}")

    def do_migrate_schema(self, arg: str) -> None:
        try:
            old_ver, new_ver = shlex.split(arg)
        except ValueError:
            print("Usage: migrate_schema <from_version> <to_version>")
            return
        try:
            DEFAULT_SCHEMA_MANAGER.upgrade_schema(old_ver, new_ver, graph=self.graph)
            print("Schema migrated.")
        except Exception as e:
            print(f"Error migrating schema: {e}")

    def do_benchmark_vectors(self, arg: str) -> None:
        parser = argparse.ArgumentParser(prog="benchmark_vectors")
        parser.add_argument("--gpu", action="store_true")
        parser.add_argument("--num-vectors", type=int, default=1000)
        parser.add_argument("--num-queries", type=int, default=100)
        parser.add_argument("--runs", type=int, default=1)
        try:
            opts = parser.parse_args(shlex.split(arg))
        except SystemExit:
            return
        try:
            result = benchmark_vector_store(
                opts.gpu,
                dim=settings.UME_VECTOR_DIM,
                num_vectors=opts.num_vectors,
                num_queries=opts.num_queries,
                runs=opts.runs,
            )
        except ImportError as exc:  # pragma: no cover - optional dependency
            if "faiss" in str(exc):
                old_backend = settings.UME_VECTOR_BACKEND
                object.__setattr__(settings, "UME_VECTOR_BACKEND", "chroma")
                try:
                    result = benchmark_vector_store(
                        opts.gpu,
                        dim=settings.UME_VECTOR_DIM,
                        num_vectors=opts.num_vectors,
                        num_queries=opts.num_queries,
                        runs=opts.runs,
                    )
                finally:
                    object.__setattr__(settings, "UME_VECTOR_BACKEND", old_backend)
            else:
                print(str(exc))
                return
        build = result.get("avg_build_time") or result.get("indexing_rate")
        if "avg_build_time" in result:
            print(f"Avg build time: {build:.3f}s")
        else:
            print(f"Indexing rate: {build} docs/s")
        print(f"Avg query latency: {result['avg_query_latency']*1000:.3f}ms")

    def do_purge_old(self, arg: str) -> None:
        parser = argparse.ArgumentParser(prog="purge_old")
        parser.add_argument("--days", type=int, default=settings.UME_GRAPH_RETENTION_DAYS)
        try:
            opts = parser.parse_args(shlex.split(arg))
        except SystemExit:
            return
        purge_method = getattr(self.base_graph, "purge_old_records", None)
        if callable(purge_method):
            purge_method(opts.days * 86400)
            print(f"Purged records older than {opts.days} days.")
        else:
            print("Purge not supported for this graph type.")

    def do_set_peer(self, arg: str) -> None:
        peer = arg.strip()
        if not peer:
            print("Usage: set_peer <bootstrap_servers>")
            return
        self.peer_cluster = peer
        print(f"Peer cluster set to {peer}")

    def do_sync(self, arg: str) -> None:
        parser = argparse.ArgumentParser(prog="sync")
        parser.add_argument("--continuous", action="store_true")
        try:
            opts = parser.parse_args(shlex.split(arg))
        except SystemExit:
            return
        if not self.peer_cluster:
            print("Peer cluster not configured. Use set_peer first.")
            return
        from ume.federation import ClusterReplicator

        replicator = ClusterReplicator(settings, self.peer_cluster)
        try:
            if opts.continuous:
                replicator.run()
            else:
                replicator.replicate_once()
        except KeyboardInterrupt:
            pass
        finally:
            replicator.stop()

    def do_mirror_topics(self, arg: str) -> None:
        if not arg.strip():
            print("Usage: mirror_topics <topic1,topic2,...>")
            return
        self.mm_topics = [t.strip() for t in arg.split(",")]
        print(f"MirrorMaker topics set to {', '.join(self.mm_topics)}")

    def do_mirror_start(self, arg: str) -> None:
        peer = self.peer_cluster
        if not peer:
            print("Peer cluster not configured. Use set_peer first.")
            return
        if self.mm_driver:
            print("MirrorMaker already running.")
            return
        self.mm_driver = MirrorMakerDriver(
            settings.KAFKA_BOOTSTRAP_SERVERS, peer, self.mm_topics
        )
        self.mm_driver.start()
        print("MirrorMaker started.")

    def do_mirror_status(self, arg: str) -> None:
        if not self.mm_driver:
            print("MirrorMaker not running.")
        else:
            print(f"MirrorMaker {self.mm_driver.status()}")

    def do_mirror_stop(self, arg: str) -> None:
        if self.mm_driver:
            self.mm_driver.stop()
            self.mm_driver = None
            print("MirrorMaker stopped.")
        else:
            print("MirrorMaker not running.")

    def do_reload_policies(self, arg: str) -> None:
        import importlib
        from ume.plugins import alignment

        importlib.reload(alignment)
        alignment.reload_plugins()
        print("Policies reloaded.")

    def do_watch(self, arg: str) -> None:
        paths = [p.strip() for p in arg.split(",")] if arg else settings.WATCH_PATHS
        from ume.watchers.dev_log_watcher import run_watcher

        run_watcher(paths)

    # ----- Utility commands -----
    def do_clear(self, arg: str) -> None:
        self.graph.clear()
        print("Graph cleared.")

    def do_exit(self, arg: str) -> bool:
        print("Goodbye!")
        return True

    def do_quit(self, arg: str) -> bool:
        return self.do_exit(arg)

    def do_EOF(self, arg: str) -> bool:
        print("\nGoodbye!")
        return True

