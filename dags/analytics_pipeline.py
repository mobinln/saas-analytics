from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import psycopg2

default_args = {
    "owner": "data-eng",
    "depends_on_past": False,
    "start_date": datetime(2024, 1, 1),
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}


def check_data_quality():
    """Run data quality checks"""
    conn = psycopg2.connect(
        host="postgres",
        database="saas_analytics",
        user="dataeng",
        password="dataeng123",
    )
    cursor = conn.cursor()

    # Check for duplicate events
    cursor.execute("""
        SELECT COUNT(*) as duplicates
        FROM (
            SELECT event_id, COUNT(*) as cnt
            FROM raw_events
            WHERE DATE(timestamp) = CURRENT_DATE
            GROUP BY event_id
            HAVING COUNT(*) > 1
        ) dups
    """)

    duplicates = cursor.fetchone()[0]

    if duplicates > 0:
        raise ValueError(f"Found {duplicates} duplicate events!")

    # Check for missing tenant data
    cursor.execute("""
        SELECT COUNT(DISTINCT tenant_id) as missing
        FROM raw_events
        WHERE tenant_id NOT IN (SELECT tenant_id FROM dim_tenants)
    """)

    missing = cursor.fetchone()[0]

    if missing > 0:
        raise ValueError(f"Found events with {missing} unknown tenants!")

    print("Data quality checks passed!")
    conn.close()


with DAG(
    "saas_analytics_pipeline",
    default_args=default_args,
    description="Daily analytics pipeline for multi-tenant SaaS",
    schedule_interval="0 1 * * *",  # Run at 1 AM daily
    catchup=False,
) as dag:
    quality_check = PythonOperator(
        task_id="check_data_quality",
        python_callable=check_data_quality,
    )

    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command="cd /path/to/saas_analytics && dbt run",
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command="cd /path/to/saas_analytics && dbt test",
    )

    quality_check >> dbt_run >> dbt_test
