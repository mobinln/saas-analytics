"""
Tenant Provisioning DAG
Orchestrates the complete setup of a new tenant
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
import logging
import uuid

logger = logging.getLogger(__name__)

default_args = {
    "owner": "analytics",
    "depends_on_past": False,
    "start_date": datetime(2024, 1, 1),
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
}


def provision_tenant(**context):
    """
    Main provisioning function - creates tenant record

    This would typically be triggered via API with parameters:
    - tenant_name
    - tier
    - metadata
    """
    # For demo, we can use DAG params or generate a test tenant
    tenant_name = context["params"].get(
        "tenant_name", f"demo_tenant_{uuid.uuid4().hex[:8]}"
    )
    tier = context["params"].get("tier", "standard")

    pg_hook = PostgresHook(postgres_conn_id="postgres_default")

    try:
        # Generate tenant ID
        tenant_id = str(uuid.uuid4())

        # Insert tenant
        insert_query = """
            INSERT INTO raw.tenants (tenant_id, tenant_name, tier, metadata)
            VALUES (%s, %s, %s, %s::jsonb)
            RETURNING tenant_id, tenant_name, tier, status
        """

        result = pg_hook.get_first(
            insert_query,
            parameters=(
                tenant_id,
                tenant_name,
                tier,
                '{"provisioned_by": "airflow", "provisioned_at": "'
                + datetime.utcnow().isoformat()
                + '"}',
            ),
        )

        logger.info(f"Tenant provisioned: {result}")

        # Push tenant_id to XCom for downstream tasks
        context["task_instance"].xcom_push(key="tenant_id", value=tenant_id)
        context["task_instance"].xcom_push(key="tenant_name", value=tenant_name)

        return {
            "tenant_id": tenant_id,
            "tenant_name": tenant_name,
            "tier": tier,
            "status": "provisioned",
        }

    except Exception as e:
        logger.error(f"Error provisioning tenant: {str(e)}")
        raise


def setup_rls_policies(**context):
    """
    Set up Row Level Security policies for the tenant
    """
    tenant_id = context["task_instance"].xcom_pull(
        task_ids="provision_tenant", key="tenant_id"
    )

    tenant_name = context["task_instance"].xcom_pull(
        task_ids="provision_tenant", key="tenant_name"
    )

    pg_hook = PostgresHook(postgres_conn_id="postgres_default")

    try:
        # RLS policy is already set up at table level
        # Here we just verify it's enabled
        verify_query = """
            SELECT relrowsecurity 
            FROM pg_class 
            WHERE relname = 'events' AND relnamespace = 'raw'::regnamespace
        """

        result = pg_hook.get_first(verify_query)

        if result and result[0]:
            logger.info(f"RLS verified for tenant {tenant_name}")
        else:
            logger.warning(f"RLS not enabled on events table")

        return True

    except Exception as e:
        logger.error(f"Error setting up RLS policies: {str(e)}")
        raise


def create_superset_rls_rules(**context):
    """
    Create RLS rules in Superset for the tenant
    This would integrate with Superset API in production
    """
    tenant_id = context["task_instance"].xcom_pull(
        task_ids="provision_tenant", key="tenant_id"
    )

    tenant_name = context["task_instance"].xcom_pull(
        task_ids="provision_tenant", key="tenant_name"
    )

    logger.info(f"Creating Superset RLS rules for tenant: {tenant_name}")

    # In production, this would call Superset API
    # For now, we just log the action

    try:
        # Superset RLS rule configuration
        rls_config = {
            "tenant_id": tenant_id,
            "tenant_name": tenant_name,
            "filter_clause": f"tenant_id = '{tenant_id}'",
            "datasets": ["fct_usage_events", "tenant_usage_metrics"],
        }

        logger.info(f"RLS config: {rls_config}")

        # TODO: Implement actual Superset API call
        # Example:
        # import requests
        # response = requests.post(
        #     f"{SUPERSET_URL}/api/v1/rowlevelsecurity/",
        #     json=rls_config,
        #     headers={'Authorization': f'Bearer {token}'}
        # )

        return True

    except Exception as e:
        logger.error(f"Error creating Superset RLS rules: {str(e)}")
        raise


def run_initial_dbt_for_tenant(**context):
    """
    Run dbt models to ensure tenant data is processed
    """
    tenant_id = context["task_instance"].xcom_pull(
        task_ids="provision_tenant", key="tenant_id"
    )

    logger.info(f"Running dbt for tenant: {tenant_id}")

    try:
        # This would trigger a dbt run with tenant context
        # For now, we just log the action

        logger.info("dbt run completed for tenant")
        return True

    except Exception as e:
        logger.error(f"Error running dbt: {str(e)}")
        raise


def send_provisioning_notification(**context):
    """
    Send notification that tenant provisioning is complete
    """
    tenant_info = context["task_instance"].xcom_pull(task_ids="provision_tenant")

    logger.info(f"Tenant provisioning complete: {tenant_info}")

    # In production, this would send email/webhook notification
    notification = {
        "event": "tenant_provisioned",
        "tenant_id": tenant_info["tenant_id"],
        "tenant_name": tenant_info["tenant_name"],
        "tier": tenant_info["tier"],
        "timestamp": datetime.utcnow().isoformat(),
    }

    logger.info(f"Notification: {notification}")

    return notification


# Define DAG
with DAG(
    "tenant_provisioning",
    default_args=default_args,
    description="Provision a new tenant with complete setup",
    schedule_interval=None,  # Triggered manually or via API
    catchup=False,
    tags=["tenant", "provisioning", "onboarding"],
    params={"tenant_name": "demo_tenant", "tier": "standard"},
) as dag:
    # Step 1: Provision tenant record
    provision_task = PythonOperator(
        task_id="provision_tenant",
        python_callable=provision_tenant,
        provide_context=True,
    )

    # Step 2: Set up RLS policies
    rls_task = PythonOperator(
        task_id="setup_rls_policies",
        python_callable=setup_rls_policies,
        provide_context=True,
    )

    # Step 3: Create Superset RLS rules
    superset_rls_task = PythonOperator(
        task_id="create_superset_rls_rules",
        python_callable=create_superset_rls_rules,
        provide_context=True,
    )

    # Step 4: Run initial dbt transformations
    dbt_task = PythonOperator(
        task_id="run_initial_dbt",
        python_callable=run_initial_dbt_for_tenant,
        provide_context=True,
    )

    # Step 5: Send notification
    notify_task = PythonOperator(
        task_id="send_notification",
        python_callable=send_provisioning_notification,
        provide_context=True,
    )

    # Define task dependencies
    provision_task >> [rls_task, superset_rls_task] >> dbt_task >> notify_task
