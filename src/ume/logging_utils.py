import logging
import structlog

from .config import settings


def configure_logging(
    *, level: int | str | None = None, json_logs: bool | None = None
) -> None:
    """Configure structlog-based logging.

    Parameters
    ----------
    level:
        Logging level, e.g. ``logging.INFO`` or ``"DEBUG"``. Defaults to the
        ``UME_LOG_LEVEL`` environment variable or ``INFO``.
    json_logs:
        If ``True``, use JSON formatted logs. Defaults to ``UME_LOG_JSON``
        environment variable (``"1"``, ``"true"``).
    """
    if level is None:
        level = settings.UME_LOG_LEVEL
    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)

    if json_logs is None:
        json_logs = settings.UME_LOG_JSON

    processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]
    renderer: structlog.types.Processor
    if json_logs:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()
    processors.append(renderer)

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(level=level, format="%(message)s")
