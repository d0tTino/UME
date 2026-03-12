"""Central deprecation registry and runtime warning policy for UME."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
import warnings

RUNTIME_WARNING_POLICY = {
    "pre_sunset": "emit DeprecationWarning on each legacy shim access",
    "post_sunset": "remove shim; if temporarily retained, emit DeprecationWarning with past-sunset marker",
}


@dataclass(frozen=True)
class DeprecationSpec:
    """Declarative metadata for one deprecated API entrypoint."""

    key: str
    replacement: str
    sunset_version: str
    sunset_date: date
    status: str
    removal_note: str | None = None


DEPRECATION_REGISTRY: dict[str, DeprecationSpec] = {
    "ume.projection_engine.run_projection_engine": DeprecationSpec(
        key="ume.projection_engine.run_projection_engine",
        replacement="ume.services.projection_worker.run_projection_worker",
        sunset_version="0.2.0",
        sunset_date=date(2026, 1, 31),
        status="removed",
        removal_note="Removed after sunset; use projection_worker entrypoint.",
    ),
    "ume.pipeline.graph_consumer.run_graph_consumer": DeprecationSpec(
        key="ume.pipeline.graph_consumer.run_graph_consumer",
        replacement="ume.pipeline.graph_consumer.run_event_pipeline_consumer",
        sunset_version="0.2.0",
        sunset_date=date(2026, 1, 31),
        status="removed",
        removal_note="Removed after sunset; renamed to explicit orchestrator consumer.",
    ),
    "ume.services.mutate.run_mutation": DeprecationSpec(
        key="ume.services.mutate.run_mutation",
        replacement="ume.services.event_processor.DEFAULT_EVENT_PROCESSOR.process_payload",
        sunset_version="0.3.0",
        sunset_date=date(2026, 7, 1),
        status="active",
    ),
    "ume.services.mutate.run_mutation_async": DeprecationSpec(
        key="ume.services.mutate.run_mutation_async",
        replacement="ume.services.event_processor.DEFAULT_EVENT_PROCESSOR.process_payload_async",
        sunset_version="0.3.0",
        sunset_date=date(2026, 7, 1),
        status="active",
    ),
    "ume.__getattr__.runtime_export_fallback": DeprecationSpec(
        key="ume.__getattr__.runtime_export_fallback",
        replacement="ume.bootstrap.runtime.bootstrap_runtime",
        sunset_version="0.3.0",
        sunset_date=date(2026, 7, 1),
        status="active",
    ),
    "ume.__getattr__.compat_exports": DeprecationSpec(
        key="ume.__getattr__.compat_exports",
        replacement="Direct module imports from canonical module paths",
        sunset_version="0.4.0",
        sunset_date=date(2026, 10, 1),
        status="active",
    ),
    "ume.stream_processor": DeprecationSpec(
        key="ume.stream_processor",
        replacement="ume.pipeline.stream_processor",
        sunset_version="0.3.0",
        sunset_date=date(2026, 7, 1),
        status="active",
    ),
}


def is_past_sunset(spec: DeprecationSpec, *, now: datetime | None = None) -> bool:
    current = (now or datetime.now(tz=UTC)).date()
    return current > spec.sunset_date


def warn_deprecated(key: str, *, detail: str | None = None, stacklevel: int = 2) -> None:
    spec = DEPRECATION_REGISTRY[key]
    message = (
        f"{spec.key} is deprecated; use {spec.replacement}. "
        f"Sunset {spec.sunset_version} ({spec.sunset_date.isoformat()})."
    )
    if detail:
        message = f"{message} {detail}"
    if is_past_sunset(spec):
        message = f"{message} [PAST_SUNSET]"
    warnings.warn(message, DeprecationWarning, stacklevel=stacklevel)
