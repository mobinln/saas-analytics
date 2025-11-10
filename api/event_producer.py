import os
import logging
import dotenv
import json
import time
from kafka import KafkaProducer
from kafka.errors import KafkaError

dotenv.load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
KAFKA_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "tenant_events")


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
