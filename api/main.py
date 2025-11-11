import uuid
from fastapi import FastAPI, Body
from datetime import datetime
from contextlib import asynccontextmanager
import json

from api.schemas import EventRequest
from api.event_producer import create_producer, KAFKA_TOPIC

kafka_producer = create_producer()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    kafka_producer.close()


app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "analytics-api",
        "version": "1.0.0",
    }


@app.post("/api/v1/event")
def save_event(event: EventRequest = Body()):
    timestamp = datetime.now()
    event_id = str(uuid.uuid4())

    event = {
        "event_id": event_id,
        "tenant_id": "TENANT_ID",
        "event_type": event.event_type,
        "event_timestamp": timestamp.isoformat(),
        "user_id": event.user_id,
        "session_id": event.session_id,
        "event_data": json.dumps(event.event_data),
    }

    kafka_producer.send(KAFKA_TOPIC, value=event)

    return {
        "detail": "done",
        "timestamp": timestamp.isoformat(),
        "event_id": event_id,
    }
