import atexit
import logging
import threading
from collections.abc import Callable

from . import Dossier

logger = logging.getLogger(__name__)

_thread: threading.Thread | None = None
_stop_event: threading.Event | None = None
_atexit_handle: Callable[[], object] | None = None
_thread_params: tuple[object, ...] | None = None

def start_dossier_snapshot_scheduler(
    dossier: Dossier,
    *,
    interval_seconds: float = 3600,
) -> tuple[threading.Thread, Callable[[], None]]:
    """Periodically call :meth:`Dossier.snapshot` in the background."""
    global _thread, _stop_event, _atexit_handle, _thread_params

    params = (dossier, interval_seconds)

    if _thread and _thread.is_alive():
        if params == _thread_params:
            return _thread, lambda: None
        stop_dossier_snapshot_scheduler()

    stop_event = threading.Event()

    def _snapshot() -> None:
        try:
            dossier.snapshot()
        except Exception:
            logger.exception("Failed to snapshot dossier at %s", dossier.root)

    def _run() -> None:
        while not stop_event.wait(interval_seconds):
            _snapshot()

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    _atexit_handle = atexit.register(_snapshot)

    _thread = thread
    _stop_event = stop_event
    _thread_params = params

    def stop() -> None:
        stop_event.set()
        thread.join()

    return thread, stop


def stop_dossier_snapshot_scheduler() -> None:
    """Stop the dossier snapshot scheduler if running."""
    global _thread, _stop_event, _atexit_handle, _thread_params

    if _stop_event is not None:
        _stop_event.set()
    if _thread is not None and _thread.is_alive():
        _thread.join()
    if _atexit_handle is not None:
        try:
            atexit.unregister(_atexit_handle)
        finally:
            _atexit_handle = None
    _thread = None
    _stop_event = None
    _thread_params = None
