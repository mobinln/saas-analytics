from prometheus_client import start_http_server, Gauge, Counter
import psycopg2
import time

# Define metrics
events_processed = Counter(
    "saas_events_processed_total", "Total events processed", ["tenant_id"]
)
active_tenants = Gauge("saas_active_tenants", "Number of active tenants")
data_freshness = Gauge(
    "saas_data_freshness_seconds", "Seconds since last event", ["tenant_id"]
)


def collect_metrics():
    """Collect metrics from database"""
    conn = psycopg2.connect(
        host="localhost",
        database="saas_analytics",
        user="dataeng",
        password="dataeng123",
    )
    cursor = conn.cursor()

    while True:
        # Count active tenants
        cursor.execute("""
            SELECT COUNT(DISTINCT tenant_id)
            FROM raw_events
            WHERE timestamp > NOW() - INTERVAL '24 hours'
        """)
        active_tenants.set(cursor.fetchone()[0])

        # Check data freshness per tenant
        cursor.execute("""
            SELECT tenant_id, 
                   EXTRACT(EPOCH FROM (NOW() - MAX(timestamp))) as seconds_old
            FROM raw_events
            GROUP BY tenant_id
        """)

        for tenant_id, seconds_old in cursor.fetchall():
            data_freshness.labels(tenant_id=tenant_id).set(seconds_old)

        time.sleep(60)  # Update every minute

    conn.close()


if __name__ == "__main__":
    start_http_server(8000)
    collect_metrics()
