"""Domain extension point contracts used by mutation and pipeline entry points."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class DomainExtension(Protocol):
    """Protocol for pluggable domain enrichment hooks."""

    def __call__(self, context: Any) -> dict[str, Any] | None:
        ...


def run_domain_extensions(context: Any, extensions: list[DomainExtension]) -> dict[str, Any]:
    """Execute domain extensions and merge returned details."""

    details: dict[str, Any] = {}
    for extension in extensions:
        extension_details = extension(context)
        if extension_details:
            details.update(extension_details)
    return details
