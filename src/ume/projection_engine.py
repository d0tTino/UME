"""Projection worker entrypoint.

This module previously exposed ``run_projection_engine`` as a compatibility shim.
The shim was removed after its deprecation sunset; use
``ume.services.projection_worker.run_projection_worker`` directly.
"""

from __future__ import annotations

from .services.projection_worker import main, run_projection_worker

__all__ = ["main", "run_projection_worker"]


if __name__ == "__main__":  # pragma: no cover - manual execution
    main()
