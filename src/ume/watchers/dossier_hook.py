from __future__ import annotations

from typing import Any

from ume.dossier import Dossier


def dossier_activity_hook(payload: dict[str, Any]) -> None:
    """Write watcher payloads to the user's dossier."""
    dossier = Dossier.load()
    dossier.add_activity(payload)
