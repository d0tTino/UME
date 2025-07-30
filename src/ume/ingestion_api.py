from __future__ import annotations

import json
import logging

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


@app.on_event("startup")
def _init_producer() -> None:
    """Initialize the Kafka producer."""
    global producer
    producer = Producer(producer_conf)


@app.post("/events", status_code=202)
async def post_event(request: Request) -> JSONResponse:
    """Validate the request body and publish it to Kafka."""
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    try:
        snake_data = event_to_snake(data)
        validate_event_dict(data)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

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


@app.on_event("shutdown")
def _close_producer() -> None:
    if producer is None:
        return
    try:
        producer.flush()
    except Exception:
        logger.exception("Producer flush failed")
