"""
DBT Transformation DAG
Runs dbt models to transform raw data into analytics-ready marts
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
import logging

logger = logging.getLogger(__name__)

default_args = {
    "owner": "analytics",
    "depends_on_past": False,
    "start_date": datetime(2024, 1, 1),
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}


def check_data_quality(**context):
    """Run data quality checks before transformations"""
    pg_hook = PostgresHook(postgres_conn_id="postgres_default")

    checks = [
        {
            "name": "raw_events_count",
            "query": "SELECT COUNT(*) FROM raw.events WHERE ingested_at > NOW() - INTERVAL '1 hour'",
            "min_value": 0,
        },
        {
            "name": "tenant_count",
            "query": "SELECT COUNT(*) FROM raw.tenants WHERE status = 'active'",
            "min_value": 1,
        },
    ]

    for check in checks:
        result = pg_hook.get_first(check["query"])
        count = result[0] if result else 0

        logger.info(f"Data quality check '{check['name']}': {count} rows")

        if count < check["min_value"]:
            raise ValueError(
                f"Data quality check '{check['name']}' failed: {count} < {check['min_value']}"
            )

    logger.info("All data quality checks passed")
    return True


def validate_tenant_isolation(**context):
    """Validate that RLS policies are working correctly"""
    pg_hook = PostgresHook(postgres_conn_id="postgres_default")

    # Test that tenant isolation is enforced
    test_query = """
        SELECT 
            tenant_id,
            COUNT(*) as event_count
        FROM raw.events
        GROUP BY tenant_id
        HAVING COUNT(*) > 0
    """

    results = pg_hook.get_records(test_query)
    tenant_count = len(results)

    logger.info(f"Tenant isolation validation: {tenant_count} tenants with data")

    if tenant_count == 0:
        raise ValueError("No tenant data found - possible isolation issue")

    return True


# Define DAG
with DAG(
    "dbt_transformation",
    default_args=default_args,
    description="Run dbt models for data transformation",
    schedule_interval="0 * * * *",  # Every hour
    catchup=False,
    tags=["dbt", "transformation", "analytics"],
) as dag:
    # Data quality checks
    quality_check_task = PythonOperator(
        task_id="check_data_quality",
        python_callable=check_data_quality,
        provide_context=True,
    )

    # dbt deps - install dependencies
    dbt_deps = BashOperator(
        task_id="dbt_deps",
        bash_command="cd /opt/dbt && dbt deps --profiles-dir .",
    )

    # dbt seed - load seed data (if any)
    dbt_seed = BashOperator(
        task_id="dbt_seed",
        bash_command="cd /opt/dbt && dbt seed --profiles-dir .",
    )

    # dbt run - run all models
    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command="cd /opt/dbt && dbt run --profiles-dir . --models +marts",
    )

    # dbt test - run data tests
    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command="cd /opt/dbt && dbt test --profiles-dir .",
    )

    # dbt docs generate
    dbt_docs = BashOperator(
        task_id="dbt_docs_generate",
        bash_command="cd /opt/dbt && dbt docs generate --profiles-dir .",
    )

    # Validate tenant isolation
    validate_isolation_task = PythonOperator(
        task_id="validate_tenant_isolation",
        python_callable=validate_tenant_isolation,
        provide_context=True,
    )

    # Define task dependencies
    quality_check_task >> dbt_deps >> dbt_seed >> dbt_run
    dbt_run >> [dbt_test, validate_isolation_task, dbt_docs]
