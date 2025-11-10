"""
Event Producer - Simulates SaaS product usage events
Generates realistic multi-tenant event data and publishes to Kafka
"""

import os
import json
import time
import random
import uuid
from datetime import datetime, timedelta
from kafka import KafkaProducer
from kafka.errors import KafkaError
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
KAFKA_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "tenant_events")
EVENTS_PER_BATCH = int(os.getenv("EVENTS_PER_BATCH", "100"))
BATCH_INTERVAL = int(os.getenv("BATCH_INTERVAL", "10"))  # seconds

# Tenant IDs (matching seed data)
TENANT_IDS = [
    "11111111-1111-1111-1111-111111111111",  # acme_corp
    "22222222-2222-2222-2222-222222222222",  # beta_inc
    "33333333-3333-3333-3333-333333333333",  # gamma_ltd
]

# Event types with weights (probability distribution)
EVENT_TYPES = [
    ("page_view", 0.40),
    ("button_click", 0.25),
    ("api_call", 0.15),
    ("feature_usage", 0.12),
    ("form_submit", 0.08),
]

# Sample data for realistic events
PAGES = [
    "/dashboard",
    "/reports",
    "/settings",
    "/users",
    "/analytics",
    "/profile",
    "/billing",
    "/integrations",
    "/help",
    "/home",
]

FEATURES = [
    "export_data",
    "create_chart",
    "share_dashboard",
    "schedule_report",
    "api_access",
    "bulk_import",
    "user_invite",
    "custom_branding",
]

DEVICES = ["desktop", "mobile", "tablet"]
BROWSERS = ["chrome", "firefox", "safari", "edge"]
COUNTRIES = ["US", "UK", "CA", "DE", "FR", "JP", "AU", "BR"]


def weighted_choice(choices):
    """Select item based on weighted probability"""
    items, weights = zip(*choices)
    return random.choices(items, weights=weights, k=1)[0]


def generate_event(tenant_id):
    """Generate a realistic usage event"""
    event_type = weighted_choice(EVENT_TYPES)
    timestamp = datetime.utcnow() - timedelta(seconds=random.randint(0, 300))

    # Generate user and session IDs with some consistency
    user_id = f"user_{tenant_id[:8]}_{random.randint(1, 50)}"
    session_id = f"session_{tenant_id[:8]}_{int(time.time() / 1800)}"  # 30min sessions

    # Base event data
    event = {
        "event_id": str(uuid.uuid4()),
        "tenant_id": tenant_id,
        "event_type": event_type,
        "event_timestamp": timestamp.isoformat(),
        "user_id": user_id,
        "session_id": session_id,
        "event_data": {
            "device_type": random.choice(DEVICES),
            "browser": random.choice(BROWSERS),
            "country": random.choice(COUNTRIES),
        },
    }

    # Add event-specific data
    if event_type == "page_view":
        event["event_data"]["page_url"] = random.choice(PAGES)
        if random.random() > 0.7:
            event["event_data"]["referrer"] = random.choice(PAGES)

    elif event_type == "feature_usage":
        event["event_data"]["feature_name"] = random.choice(FEATURES)
        event["event_data"]["duration_seconds"] = random.randint(5, 300)

    elif event_type == "api_call":
        event["event_data"]["endpoint"] = (
            f"/api/v1/{random.choice(['data', 'users', 'reports'])}"
        )
        event["event_data"]["method"] = random.choice(["GET", "POST", "PUT"])
        event["event_data"]["status_code"] = random.choices(
            [200, 201, 400, 404, 500], weights=[0.85, 0.05, 0.05, 0.03, 0.02]
        )[0]
        event["event_data"]["response_time_ms"] = random.randint(50, 2000)

    elif event_type == "button_click":
        event["event_data"]["button_id"] = (
            f"btn_{random.choice(['save', 'cancel', 'submit', 'export', 'share'])}"
        )
        event["event_data"]["page_url"] = random.choice(PAGES)

    elif event_type == "form_submit":
        event["event_data"]["form_type"] = random.choice(
            ["contact", "settings", "profile", "feedback"]
        )
        event["event_data"]["fields_count"] = random.randint(3, 15)
        event["event_data"]["validation_errors"] = random.randint(0, 3)

    return event


def create_producer():
    """Create Kafka producer with retry logic"""
    max_retries = 5
    retry_delay = 5

    for attempt in range(max_retries):
        try:
            producer = KafkaProducer(
                bootstrap_servers=KAFKA_SERVERS,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                acks="all",
                retries=3,
                max_in_flight_requests_per_connection=1,
                compression_type="gzip",
            )
            logger.info(f"Successfully connected to Kafka at {KAFKA_SERVERS}")
            return producer
        except KafkaError as e:
            logger.warning(f"Attempt {attempt + 1}/{max_retries} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                raise


def main():
    """Main event generation loop"""
    logger.info("Starting event producer...")
    logger.info(f"Kafka servers: {KAFKA_SERVERS}")
    logger.info(f"Topic: {KAFKA_TOPIC}")
    logger.info(f"Events per batch: {EVENTS_PER_BATCH}")
    logger.info(f"Batch interval: {BATCH_INTERVAL}s")

    producer = create_producer()

    try:
        batch_count = 0
        total_sent = 0

        while True:
            batch_start = time.time()
            batch_events = []

            # Generate events for all tenants with varying volumes
            for tenant_id in TENANT_IDS:
                # Enterprise tenants generate more events
                multiplier = 2.0 if tenant_id.startswith("11111111") else 1.0
                num_events = int(EVENTS_PER_BATCH * multiplier / len(TENANT_IDS))

                for _ in range(num_events):
                    event = generate_event(tenant_id)
                    batch_events.append(event)

            # Send events to Kafka
            for event in batch_events:
                try:
                    future = producer.send(KAFKA_TOPIC, value=event)
                    # Block to ensure delivery
                    future.get(timeout=10)
                except KafkaError as e:
                    logger.error(f"Failed to send event: {e}")

            total_sent += len(batch_events)
            batch_count += 1

            batch_duration = time.time() - batch_start
            logger.info(
                f"Batch {batch_count}: Sent {len(batch_events)} events "
                f"in {batch_duration:.2f}s (Total: {total_sent})"
            )

            # Wait for next batch
            sleep_time = max(0, BATCH_INTERVAL - batch_duration)
            if sleep_time > 0:
                time.sleep(sleep_time)

    except KeyboardInterrupt:
        logger.info("Shutting down event producer...")
    finally:
        producer.close()
        logger.info(f"Event producer stopped. Total events sent: {total_sent}")


if __name__ == "__main__":
    main()
