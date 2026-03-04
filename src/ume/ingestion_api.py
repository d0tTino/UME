from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from jsonschema import ValidationError
from confluent_kafka import Producer, KafkaException

from .config import settings
from .schema_utils import validate_event_dict
from .metrics import INGEST_EVENTS_TOTAL
from .logging_utils import configure_logging
from .utils import ssl_config, event_to_snake

configure_logging()
logger = logging.getLogger(__name__)

producer_conf = {"bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS}
producer_conf.update(ssl_config())
producer: Producer | None = None

app = FastAPI(
    title="UME Ingestion API",
    version="0.1.0",
    description="Publish raw events to Kafka",
)


@app.on_event("startup")  # type: ignore[misc]
def _init_producer() -> None:
    """Initialize the Kafka producer."""
    global producer
    producer = Producer(producer_conf)


@app.post("/events", status_code=202)  # type: ignore[misc]
async def post_event(request: Request) -> JSONResponse:
    """Validate the request body and publish it to Kafka."""
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    try:
        validate_event_dict(data)
    except ValidationError as exc:
        if not settings.UME_INGEST_LENIENT_VALIDATION:
            raise HTTPException(status_code=400, detail=_validation_error_detail(exc))
        return _publish_quarantined_event(data, exc)

    snake_data = event_to_snake(data)

    if producer is None:
        raise HTTPException(status_code=503, detail="Producer not initialized")
    try:
        producer.produce(
            settings.KAFKA_RAW_EVENTS_TOPIC,
            json.dumps(data).encode("utf-8"),
        )
        producer.poll(0)  # Trigger delivery callbacks without blocking
        INGEST_EVENTS_TOTAL.labels(event_type=snake_data["event_type"]).inc()
    except KafkaException as exc:
        logger.error("Failed to produce event: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to publish event")

    return JSONResponse(status_code=202, content={"status": "accepted"})


def _event_type_for_metric(data: dict[str, Any]) -> str:
    event_type = data.get("eventType") or data.get("event_type")
    if isinstance(event_type, str) and event_type:
        return event_type.lower()
    return "invalid"


def _validation_error_detail(exc: ValidationError) -> dict[str, Any]:
    return {
        "error": "event validation failed",
        "message": exc.message,
        "path": [str(item) for item in exc.path],
        "schema_path": [str(item) for item in exc.schema_path],
        "validator": exc.validator,
        "validator_value": exc.validator_value,
    }


def _publish_quarantined_event(data: dict[str, Any], exc: ValidationError) -> JSONResponse:
    if producer is None:
        raise HTTPException(status_code=503, detail="Producer not initialized")

    quarantine_message = {
        "error": _validation_error_detail(exc),
        "event": data,
        "ingestion": {"mode": "lenient", "reason": "validation_failed"},
    }
    try:
        producer.produce(
            settings.KAFKA_QUARANTINE_TOPIC,
            json.dumps(quarantine_message).encode("utf-8"),
        )
        producer.poll(0)
        INGEST_EVENTS_TOTAL.labels(event_type=_event_type_for_metric(data)).inc()
    except KafkaException as kafka_exc:
        logger.error("Failed to publish quarantined event: %s", kafka_exc)
        raise HTTPException(status_code=500, detail="Failed to publish event")

    return JSONResponse(status_code=202, content={"status": "quarantined"})


@app.on_event("shutdown")  # type: ignore[misc]
def _close_producer() -> None:
    if producer is None:
        return
    try:
        producer.flush()
    except Exception:
        logger.exception("Producer flush failed")
