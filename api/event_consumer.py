import os
import json
import logging
import signal
import sys
from kafka import KafkaConsumer
import psycopg2
from psycopg2.extras import execute_batch

import dotenv

dotenv.load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Configuration
KAFKA_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "tenant_events")
KAFKA_GROUP = "postgres-sink-group"
DB_CONFIG = f"dbname={os.getenv('POSTGRES_DB')} user={os.getenv('POSTGRES_USER')} password={os.getenv('POSTGRES_PASSWORD')} host={os.getenv('POSTGRES_HOST')}"
BATCH_SIZE = 100


class EventConsumer:
    def __init__(self):
        self.running = False
        self.consumer = None
        self.conn = None

    def connect(self):
        """Initialize Kafka and DB connections"""
        try:
            self.consumer = KafkaConsumer(
                KAFKA_TOPIC,
                bootstrap_servers=KAFKA_SERVERS,
                group_id=KAFKA_GROUP,
                enable_auto_commit=False,
                value_deserializer=lambda m: json.loads(m.decode("utf-8")),
                max_poll_records=BATCH_SIZE,
            )
            logger.info("Kafka consumer connected")

            self.conn = psycopg2.connect(DB_CONFIG)
            logger.info("Database connected")

        except Exception as e:
            logger.error(f"Connection failed: {e}")
            raise

    def process_batch(self, messages):
        """Process and insert batch of messages"""
        if not messages:
            return True

        insert_query = """
            INSERT INTO tenant_events_raw
            (event_id, tenant_id, event_type, event_timestamp, user_id, session_id, event_data)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (event_id) DO NOTHING
        """

        try:
            cursor = self.conn.cursor()

            # Prepare batch data
            batch_data = []
            for msg in messages:
                event = msg.value
                batch_data.append(
                    (
                        event["event_id"],
                        event["tenant_id"],
                        event["event_type"],
                        event["event_timestamp"],
                        event["user_id"],
                        event["session_id"],
                        json.dumps(event["event_data"]),
                    )
                )

            # Execute batch insert
            execute_batch(cursor, insert_query, batch_data)
            self.conn.commit()
            cursor.close()

            logger.info(f"Inserted {len(messages)} events")
            return True

        except Exception as e:
            logger.error(f"Batch insert failed: {e}")
            self.conn.rollback()
            return False

    def start(self):
        """Start consuming messages"""
        # Handle shutdown signals
        signal.signal(signal.SIGINT, lambda s, f: setattr(self, "running", False))
        signal.signal(signal.SIGTERM, lambda s, f: setattr(self, "running", False))

        self.connect()
        self.running = True
        logger.info("Starting consumer...")

        try:
            batch = []

            while self.running:
                # Poll messages
                messages = self.consumer.poll(timeout_ms=5000, max_records=BATCH_SIZE)

                for topic_partition, partition_messages in messages.items():
                    batch.extend(partition_messages)

                # Process when batch is full or after timeout
                if len(batch) >= BATCH_SIZE or (batch and not messages):
                    if self.process_batch(batch):
                        self.consumer.commit()
                    else:
                        logger.error("Failed to process batch, not committing")
                    batch = []

        except Exception as e:
            logger.error(f"Consumer error: {e}", exc_info=True)

        finally:
            self.cleanup()

    def cleanup(self):
        """Close connections"""
        logger.info("Shutting down...")
        if self.consumer:
            self.consumer.close()
        if self.conn:
            self.conn.close()
        logger.info("Shutdown complete")


if __name__ == "__main__":
    consumer = EventConsumer()
    try:
        consumer.start()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
