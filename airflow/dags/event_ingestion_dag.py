"""
Event Ingestion DAG
Consumes events from Kafka and loads them into PostgreSQL raw layer
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from kafka import KafkaConsumer
import json
import logging

logger = logging.getLogger(__name__)

default_args = {
    "owner": "analytics",
    "depends_on_past": False,
    "start_date": datetime(2024, 1, 1),
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
}


def consume_and_load_events(**context):
    """
    Consume events from Kafka and batch insert into PostgreSQL
    """
    import os

    kafka_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
    topic = "tenant_events"
    batch_size = 1000
    timeout_ms = 10000

    logger.info(f"Connecting to Kafka: {kafka_servers}, topic: {topic}")

    # Create Kafka consumer
    consumer = KafkaConsumer(
        topic,
        bootstrap_servers=kafka_servers,
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        group_id="airflow_ingestion",
        value_deserializer=lambda x: json.loads(x.decode("utf-8")),
        consumer_timeout_ms=timeout_ms,
    )

    # Get PostgreSQL hook
    pg_hook = PostgresHook(postgres_conn_id="postgres_default")
    conn = pg_hook.get_conn()
    cursor = conn.cursor()

    events_batch = []
    total_ingested = 0

    try:
        for message in consumer:
            event = message.value

            # Validate required fields
            if not all(
                k in event for k in ["tenant_id", "event_type", "event_timestamp"]
            ):
                logger.warning(f"Invalid event structure: {event}")
                continue

            events_batch.append(
                (
                    event["tenant_id"],
                    event["event_type"],
                    event["event_timestamp"],
                    event.get("user_id"),
                    event.get("session_id"),
                    json.dumps(event.get("event_data", {})),
                )
            )

            # Batch insert
            if len(events_batch) >= batch_size:
                insert_events(cursor, events_batch)
                conn.commit()
                total_ingested += len(events_batch)
                logger.info(
                    f"Inserted batch of {len(events_batch)} events. Total: {total_ingested}"
                )
                events_batch = []

        # Insert remaining events
        if events_batch:
            insert_events(cursor, events_batch)
            conn.commit()
            total_ingested += len(events_batch)
            logger.info(
                f"Inserted final batch of {len(events_batch)} events. Total: {total_ingested}"
            )

        logger.info(f"Event ingestion completed. Total events: {total_ingested}")

        # Push to XCom for monitoring
        context["task_instance"].xcom_push(key="events_ingested", value=total_ingested)

    except Exception as e:
        logger.error(f"Error during event ingestion: {str(e)}")
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()
        consumer.close()

    return total_ingested


def insert_events(cursor, events):
    """Batch insert events into PostgreSQL"""
    insert_query = """
        INSERT INTO raw.events (tenant_id, event_type, event_timestamp, user_id, session_id, event_data)
        VALUES (%s, %s, %s, %s, %s, %s::jsonb)
    """
    cursor.executemany(insert_query, events)


def update_tenant_summary(**context):
    """Refresh materialized view for tenant summary"""
    pg_hook = PostgresHook(postgres_conn_id="postgres_default")

    try:
        pg_hook.run("SELECT refresh_tenant_summary();")
        logger.info("Tenant summary materialized view refreshed successfully")
    except Exception as e:
        logger.error(f"Error refreshing tenant summary: {str(e)}")
        raise


# Define DAG
with DAG(
    "event_ingestion",
    default_args=default_args,
    description="Ingest events from Kafka to PostgreSQL",
    schedule_interval="*/5 * * * *",  # Every 5 minutes
    catchup=False,
    tags=["kafka", "ingestion", "events"],
) as dag:
    ingest_events_task = PythonOperator(
        task_id="consume_and_load_events",
        python_callable=consume_and_load_events,
        provide_context=True,
    )

    refresh_summary_task = PythonOperator(
        task_id="update_tenant_summary",
        python_callable=update_tenant_summary,
        provide_context=True,
    )

    ingest_events_task >> refresh_summary_task
