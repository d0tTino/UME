from __future__ import annotations

"""Simple role-based policy helpers."""


def can_read_projects(role: str, shareable: bool = False) -> bool:
    """Return ``True`` if ``role`` may view dossier projects."""
    if shareable:
        return True
    return role == "ProjectManager"


def can_read_reflections(role: str, shareable: bool = False) -> bool:
    """Return ``True`` if ``role`` may view dossier reflections."""
    if shareable:
        return True
    return role in {"ProjectManager", "Viewer"}


def can_modify_telemetry(role: str) -> bool:
    """Return ``True`` if ``role`` may update telemetry data."""
    return role == "TelemetryAdmin"
