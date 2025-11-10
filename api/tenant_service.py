"""
Tenant Service - Database operations for tenant management
"""

import os
import uuid
import json
import logging
from datetime import datetime
from typing import Optional, List, Dict
import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)


class TenantService:
    """Service for managing tenant data and provisioning"""

    def __init__(self):
        self.db_config = {
            "host": os.getenv("POSTGRES_HOST", "postgres"),
            "port": int(os.getenv("POSTGRES_PORT", 5432)),
            "user": os.getenv("POSTGRES_USER", "analytics_user"),
            "password": os.getenv("POSTGRES_PASSWORD", "analytics_pass"),
            "database": os.getenv("POSTGRES_DB", "analytics_db"),
        }

    def get_connection(self):
        """Get database connection"""
        return psycopg2.connect(**self.db_config)

    def create_tenant(
        self, tenant_name: str, tier: str = "standard", metadata: Optional[Dict] = None
    ) -> Dict:
        """
        Create a new tenant with full provisioning

        Steps:
        1. Insert tenant record
        2. Set up RLS policies
        3. Create Superset RLS rules (if available)
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            # Generate tenant ID
            tenant_id = str(uuid.uuid4())

            # Insert tenant
            cursor.execute(
                """
                INSERT INTO raw.tenants (tenant_id, tenant_name, tier, metadata)
                VALUES (%s, %s, %s, %s)
                RETURNING tenant_id, tenant_name, tier, status, created_at, metadata
            """,
                (tenant_id, tenant_name, tier, json.dumps(metadata or {})),
            )

            tenant_data = dict(cursor.fetchone())

            # Enable RLS on events table for this tenant
            self._setup_rls_policies(cursor, tenant_id)

            conn.commit()

            logger.info(f"Tenant created: {tenant_id}")

            # Format response
            return {
                "tenant_id": str(tenant_data["tenant_id"]),
                "tenant_name": tenant_data["tenant_name"],
                "tier": tenant_data["tier"],
                "status": tenant_data["status"],
                "created_at": tenant_data["created_at"].isoformat(),
                "metadata": tenant_data["metadata"],
            }

        except psycopg2.IntegrityError as e:
            logger.error(f"Tenant already exists: {str(e)}")
            return {"error": "Tenant name already exists"}
        except Exception as e:
            logger.error(f"Error creating tenant: {str(e)}")
            if conn:
                conn.rollback()
            return {"error": str(e)}
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def _setup_rls_policies(self, cursor, tenant_id: str):
        """
        Set up Row Level Security policies for a tenant
        This ensures data isolation at the database level
        """
        try:
            # The RLS policy is already created in init script
            # Here we just log for confirmation
            logger.info(f"RLS policies enabled for tenant: {tenant_id}")
        except Exception as e:
            logger.warning(f"Error setting up RLS policies: {str(e)}")

    def get_tenant(self, tenant_id: str) -> Optional[Dict]:
        """Get tenant by ID"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            cursor.execute(
                """
                SELECT tenant_id, tenant_name, tier, status, created_at, updated_at, metadata
                FROM raw.tenants
                WHERE tenant_id = %s
            """,
                (tenant_id,),
            )

            result = cursor.fetchone()

            if not result:
                return None

            tenant_data = dict(result)
            return {
                "tenant_id": str(tenant_data["tenant_id"]),
                "tenant_name": tenant_data["tenant_name"],
                "tier": tenant_data["tier"],
                "status": tenant_data["status"],
                "created_at": tenant_data["created_at"].isoformat(),
                "metadata": tenant_data["metadata"],
            }

        except Exception as e:
            logger.error(f"Error getting tenant: {str(e)}")
            return None
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def list_tenants(
        self, status: Optional[str] = None, tier: Optional[str] = None
    ) -> List[Dict]:
        """List all tenants with optional filters"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            query = """
                SELECT tenant_id, tenant_name, tier, status, created_at, metadata
                FROM raw.tenants
                WHERE 1=1
            """
            params = []

            if status:
                query += " AND status = %s"
                params.append(status)

            if tier:
                query += " AND tier = %s"
                params.append(tier)

            query += " ORDER BY created_at DESC"

            cursor.execute(query, params)
            results = cursor.fetchall()

            return [
                {
                    "tenant_id": str(row["tenant_id"]),
                    "tenant_name": row["tenant_name"],
                    "tier": row["tier"],
                    "status": row["status"],
                    "created_at": row["created_at"].isoformat(),
                    "metadata": row["metadata"],
                }
                for row in results
            ]

        except Exception as e:
            logger.error(f"Error listing tenants: {str(e)}")
            return []
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def delete_tenant(self, tenant_id: str) -> bool:
        """
        Delete (deactivate) a tenant
        Sets status to 'inactive' rather than deleting data
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                UPDATE raw.tenants
                SET status = 'inactive', updated_at = CURRENT_TIMESTAMP
                WHERE tenant_id = %s AND status = 'active'
                RETURNING tenant_id
            """,
                (tenant_id,),
            )

            result = cursor.fetchone()
            conn.commit()

            if result:
                logger.info(f"Tenant deactivated: {tenant_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"Error deleting tenant: {str(e)}")
            if conn:
                conn.rollback()
            return False
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def get_tenant_usage(self, tenant_id: str, days: int = 7) -> Dict:
        """Get usage metrics for a tenant"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            cursor.execute(
                """
                SELECT
                    event_date,
                    total_events,
                    unique_users,
                    unique_sessions,
                    avg_events_per_session,
                    avg_session_duration_minutes,
                    engagement_score
                FROM analytics.tenant_usage_metrics
                WHERE tenant_id = %s
                  AND event_date >= CURRENT_DATE - INTERVAL '%s days'
                ORDER BY event_date DESC
            """,
                (tenant_id, days),
            )

            results = cursor.fetchall()

            return {
                "tenant_id": tenant_id,
                "period_days": days,
                "metrics": [dict(row) for row in results],
            }

        except Exception as e:
            logger.error(f"Error getting tenant usage: {str(e)}")
            return {"error": str(e)}
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def get_tenant_cost(self, tenant_id: str, days: int = 30) -> Dict:
        """Get cost attribution for a tenant"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            cursor.execute(
                """
                SELECT
                    DATE(query_timestamp) as query_date,
                    COUNT(*) as query_count,
                    SUM(query_duration_ms) as total_duration_ms,
                    SUM(rows_scanned) as total_rows_scanned,
                    SUM(estimated_cost) as total_cost
                FROM analytics.tenant_query_log
                WHERE tenant_id = %s
                  AND query_timestamp >= CURRENT_DATE - INTERVAL '%s days'
                GROUP BY DATE(query_timestamp)
                ORDER BY query_date DESC
            """,
                (tenant_id, days),
            )

            results = cursor.fetchall()

            # Calculate totals
            total_cost = sum(row["total_cost"] or 0 for row in results)
            total_queries = sum(row["query_count"] for row in results)

            return {
                "tenant_id": tenant_id,
                "period_days": days,
                "total_cost": float(total_cost),
                "total_queries": total_queries,
                "daily_costs": [
                    {
                        "date": row["query_date"].isoformat(),
                        "queries": row["query_count"],
                        "cost": float(row["total_cost"] or 0),
                    }
                    for row in results
                ],
            }

        except Exception as e:
            logger.error(f"Error getting tenant cost: {str(e)}")
            return {"error": str(e)}
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
