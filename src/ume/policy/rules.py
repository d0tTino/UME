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


def can_read_skills(role: str, shareable: bool = False) -> bool:
    """Return ``True`` if ``role`` may view dossier skills."""
    if shareable:
        return True
    return role in {"ProjectManager", "Viewer"}


def can_read_values(role: str, shareable: bool = False) -> bool:
    """Return ``True`` if ``role`` may view dossier values."""
    if shareable:
        return True
    return role in {"ProjectManager", "Viewer"}


def can_read_memories(role: str, shareable: bool = False) -> bool:
    """Return ``True`` if ``role`` may view dossier memories."""
    if shareable:
        return True
    return role in {"ProjectManager", "Viewer"}


def can_modify_telemetry(role: str) -> bool:
    """Return ``True`` if ``role`` may update telemetry data."""
    return role == "TelemetryAdmin"
