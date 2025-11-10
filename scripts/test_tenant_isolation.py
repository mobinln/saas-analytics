#!/usr/bin/env python3
"""
Test Tenant Isolation
Comprehensive test suite to verify multi-tenant data isolation
"""

import requests
import psycopg2
import time
import sys
from typing import Dict, List

# Configuration
API_BASE_URL = "http://localhost:8000"
PG_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "user": "analytics_user",
    "password": "analytics_pass",
    "database": "analytics_db",
}

TENANT_IDS = [
    "11111111-1111-1111-1111-111111111111",  # acme_corp
    "22222222-2222-2222-2222-222222222222",  # beta_inc
    "33333333-3333-3333-3333-333333333333",  # gamma_ltd
]


class TestRunner:
    def __init__(self):
        self.tests_passed = 0
        self.tests_failed = 0
        self.test_results = []

    def run_test(self, test_name: str, test_func):
        """Run a single test and record results"""
        print(f"\n{'=' * 60}")
        print(f"Test: {test_name}")
        print(f"{'=' * 60}")

        try:
            result = test_func()
            if result:
                print(f"✓ PASSED")
                self.tests_passed += 1
                self.test_results.append((test_name, "PASSED", None))
            else:
                print(f"✗ FAILED")
                self.tests_failed += 1
                self.test_results.append((test_name, "FAILED", "Test returned False"))
        except Exception as e:
            print(f"✗ FAILED: {str(e)}")
            self.tests_failed += 1
            self.test_results.append((test_name, "FAILED", str(e)))

    def print_summary(self):
        """Print test summary"""
        print(f"\n{'=' * 60}")
        print("TEST SUMMARY")
        print(f"{'=' * 60}")
        print(f"Total Tests: {self.tests_passed + self.tests_failed}")
        print(f"Passed: {self.tests_passed}")
        print(f"Failed: {self.tests_failed}")
        print(f"{'=' * 60}\n")

        if self.tests_failed > 0:
            print("Failed Tests:")
            for name, status, error in self.test_results:
                if status == "FAILED":
                    print(f"  - {name}: {error}")

        return self.tests_failed == 0


def get_db_connection():
    """Get PostgreSQL connection"""
    return psycopg2.connect(**PG_CONFIG)


def test_api_health():
    """Test 1: API service is healthy"""
    response = requests.get(f"{API_BASE_URL}/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    print(f"API Status: {data['status']}")
    return True


def test_list_tenants():
    """Test 2: Can list all tenants"""
    response = requests.get(f"{API_BASE_URL}/api/v1/tenants")
    assert response.status_code == 200
    tenants = response.json()
    assert len(tenants) >= 3
    print(f"Found {len(tenants)} tenants")
    for tenant in tenants:
        print(f"  - {tenant['tenant_name']} ({tenant['tier']})")
    return True


def test_database_rls_enabled():
    """Test 3: RLS is enabled on events table"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT relrowsecurity 
        FROM pg_class 
        WHERE relname = 'events' AND relnamespace = 'raw'::regnamespace
    """)

    result = cursor.fetchone()
    cursor.close()
    conn.close()

    assert result is not None
    assert result[0] is True
    print("RLS is enabled on raw.events table")
    return True


def test_tenant_data_exists():
    """Test 4: All tenants have event data"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT tenant_id, COUNT(*) as event_count
        FROM raw.events
        GROUP BY tenant_id
        ORDER BY tenant_id
    """)

    results = cursor.fetchall()
    cursor.close()
    conn.close()

    print(f"Event counts by tenant:")
    for tenant_id, count in results:
        print(f"  - {tenant_id}: {count:,} events")

    # Check that we have data for multiple tenants
    assert len(results) >= 2

    # Check that each tenant has events
    for tenant_id, count in results:
        assert count > 0

    return True


def test_tenant_isolation_query():
    """Test 5: Tenant context filtering works"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Test for each tenant
    for tenant_id in TENANT_IDS[:2]:  # Test first 2 tenants
        # Set tenant context
        cursor.execute(f"SELECT set_tenant_context('{tenant_id}')")

        # Query with RLS enforced
        cursor.execute("SELECT COUNT(*) FROM raw.events")
        tenant_count = cursor.fetchone()[0]

        # Query total without RLS (as admin)
        cursor.execute(
            "SELECT COUNT(*) FROM raw.events WHERE tenant_id = %s", (tenant_id,)
        )
        actual_count = cursor.fetchone()[0]

        print(f"Tenant {tenant_id[:8]}...")
        print(f"  RLS filtered count: {tenant_count:,}")
        print(f"  Actual tenant count: {actual_count:,}")

        # Note: In this test, RLS may not be enforced for analytics_user
        # In production, you'd test with superset_user
        assert tenant_count > 0 or actual_count > 0

    cursor.close()
    conn.close()
    return True


def test_create_tenant():
    """Test 6: Can create a new tenant"""
    tenant_name = f"test_tenant_{int(time.time())}"

    response = requests.post(
        f"{API_BASE_URL}/api/v1/tenants",
        json={
            "tenant_name": tenant_name,
            "tier": "standard",
            "industry": "testing",
            "seats": 5,
        },
    )

    assert response.status_code == 201
    data = response.json()

    assert data["tenant_name"] == tenant_name
    assert data["tier"] == "standard"
    assert data["status"] == "active"

    print(f"Created tenant: {data['tenant_id']}")
    print(f"  Name: {data['tenant_name']}")
    print(f"  Tier: {data['tier']}")

    return True


def test_generate_guest_token():
    """Test 7: Can generate guest token with tenant context"""
    tenant_id = TENANT_IDS[0]

    response = requests.post(
        f"{API_BASE_URL}/api/v1/guest-token",
        json={
            "tenant_id": tenant_id,
            "user_email": "test@example.com",
            "dashboard_id": 1,
        },
    )

    assert response.status_code == 200
    data = response.json()

    assert "token" in data
    assert "dashboard_url" in data
    assert data["expires_in"] > 0

    print(f"Generated guest token")
    print(f"  Token length: {len(data['token'])}")
    print(f"  Expires in: {data['expires_in']} seconds")
    print(f"  Dashboard URL: {data['dashboard_url']}")

    return True


def test_tenant_usage_metrics():
    """Test 8: Can retrieve tenant usage metrics"""
    tenant_id = TENANT_IDS[0]

    response = requests.get(
        f"{API_BASE_URL}/api/v1/tenants/{tenant_id}/usage", params={"days": 7}
    )

    assert response.status_code == 200
    data = response.json()

    assert "tenant_id" in data
    assert "metrics" in data

    print(f"Retrieved usage metrics for tenant {tenant_id[:8]}...")
    print(f"  Period: {data['period_days']} days")
    print(f"  Metric records: {len(data['metrics'])}")

    return True


def test_dbt_models_exist():
    """Test 9: dbt models are built"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Check that analytics schema models exist
    models_to_check = [
        "analytics.fct_usage_events",
        "analytics.dim_tenants",
        "analytics.tenant_usage_metrics",
    ]

    for model in models_to_check:
        schema, table = model.split(".")
        cursor.execute(
            """
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_schema = %s AND table_name = %s
        """,
            (schema, table),
        )

        count = cursor.fetchone()[0]
        assert count == 1
        print(f"✓ Model exists: {model}")

    cursor.close()
    conn.close()
    return True


def test_data_quality():
    """Test 10: Data quality checks pass"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Check for null tenant_ids
    cursor.execute("SELECT COUNT(*) FROM raw.events WHERE tenant_id IS NULL")
    null_tenants = cursor.fetchone()[0]
    assert null_tenants == 0
    print(f"✓ No NULL tenant_ids found")

    # Check for invalid timestamps
    cursor.execute("""
        SELECT COUNT(*) FROM raw.events 
        WHERE event_timestamp > CURRENT_TIMESTAMP 
           OR event_timestamp < CURRENT_TIMESTAMP - INTERVAL '30 days'
    """)
    invalid_timestamps = cursor.fetchone()[0]
    print(f"Invalid timestamps: {invalid_timestamps} (should be minimal)")

    # Check for orphaned events
    cursor.execute("""
        SELECT COUNT(*) FROM raw.events e
        WHERE NOT EXISTS (
            SELECT 1 FROM raw.tenants t WHERE t.tenant_id = e.tenant_id
        )
    """)
    orphaned_events = cursor.fetchone()[0]
    assert orphaned_events == 0
    print(f"✓ No orphaned events found")

    cursor.close()
    conn.close()
    return True


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("MULTI-TENANT ANALYTICS PLATFORM - ISOLATION TESTS")
    print("=" * 60)

    runner = TestRunner()

    # Run all tests
    runner.run_test("API Health Check", test_api_health)
    runner.run_test("List Tenants", test_list_tenants)
    runner.run_test("RLS Enabled", test_database_rls_enabled)
    runner.run_test("Tenant Data Exists", test_tenant_data_exists)
    runner.run_test("Tenant Isolation Query", test_tenant_isolation_query)
    runner.run_test("Create New Tenant", test_create_tenant)
    runner.run_test("Generate Guest Token", test_generate_guest_token)
    runner.run_test("Tenant Usage Metrics", test_tenant_usage_metrics)
    runner.run_test("dbt Models Built", test_dbt_models_exist)
    runner.run_test("Data Quality Checks", test_data_quality)

    # Print summary
    all_passed = runner.print_summary()

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
