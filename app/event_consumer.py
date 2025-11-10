import json
import psycopg2
from kafka import KafkaConsumer
from datetime import datetime

# Database connection
conn = psycopg2.connect(
    host="localhost",
    port=5432,
    database="saas_analytics",
    user="dataeng",
    password="dataeng123",
)
conn.autocommit = True
cursor = conn.cursor()

# Create raw events table
cursor.execute("""
CREATE TABLE IF NOT EXISTS raw_events (
    event_id VARCHAR(36) PRIMARY KEY,
    tenant_id VARCHAR(50) NOT NULL,
    user_id VARCHAR(36) NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    properties JSONB,
    tenant_metadata JSONB,
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_tenant_timestamp 
ON raw_events(tenant_id, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_event_type 
ON raw_events(event_type);
""")

# Create tenants dimension table
cursor.execute("""
CREATE TABLE IF NOT EXISTS dim_tenants (
    tenant_id VARCHAR(50) PRIMARY KEY,
    tenant_name VARCHAR(255) NOT NULL,
    plan VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
""")

# Create users dimension table
cursor.execute("""
CREATE TABLE IF NOT EXISTS dim_users (
    user_id VARCHAR(36) PRIMARY KEY,
    tenant_id VARCHAR(50) NOT NULL,
    email VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES dim_tenants(tenant_id)
);

CREATE INDEX IF NOT EXISTS idx_users_tenant 
ON dim_users(tenant_id);
""")

print("Database tables created successfully")


def consume_events():
    """Consume events from Kafka and insert into PostgreSQL"""
    consumer = KafkaConsumer(
        "saas_events",
        bootstrap_servers=["localhost:19092"],
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        group_id="postgres_consumer",
        auto_offset_reset="earliest",
    )

    print("Starting event consumption...")
    batch = []
    batch_size = 100

    try:
        for message in consumer:
            event = message.value
            batch.append(event)

            if len(batch) >= batch_size:
                insert_batch(batch)
                batch = []

    except KeyboardInterrupt:
        if batch:
            insert_batch(batch)
        print("\nStopping consumer...")
        consumer.close()


def insert_batch(events):
    """Batch insert events"""
    try:
        for event in events:
            cursor.execute(
                """
                INSERT INTO raw_events 
                (event_id, tenant_id, user_id, event_type, timestamp, properties, tenant_metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (event_id) DO NOTHING
            """,
                (
                    event["event_id"],
                    event["tenant_id"],
                    event["user_id"],
                    event["event_type"],
                    event["timestamp"],
                    json.dumps(event["properties"]),
                    json.dumps(event["tenant_metadata"]),
                ),
            )

        print(f"Inserted batch of {len(events)} events")

    except Exception as e:
        print(f"Error inserting batch: {e}")
        conn.rollback()


if __name__ == "__main__":
    # Load and insert tenant/user seed data first
    with open("tenants.json", "r") as f:
        tenants = json.load(f)
        for tenant in tenants:
            cursor.execute(
                """
                INSERT INTO dim_tenants (tenant_id, tenant_name, plan)
                VALUES (%s, %s, %s)
                ON CONFLICT (tenant_id) DO UPDATE 
                SET tenant_name = EXCLUDED.tenant_name, 
                    plan = EXCLUDED.plan,
                    updated_at = CURRENT_TIMESTAMP
            """,
                (tenant["tenant_id"], tenant["name"], tenant["plan"]),
            )

    with open("users.json", "r") as f:
        users_by_tenant = json.load(f)
        for tenant_id, users in users_by_tenant.items():
            for user in users:
                cursor.execute(
                    """
                    INSERT INTO dim_users (user_id, tenant_id, email, name, role)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (user_id) DO NOTHING
                """,
                    (
                        user["user_id"],
                        tenant_id,
                        user["email"],
                        user["name"],
                        user["role"],
                    ),
                )

    print("Seed data loaded")

    # Start consuming
    consume_events()
