"""
RLS Manager for Superset
Manages Row Level Security rules for multi-tenant isolation
"""

from typing import Optional, Dict, List
import logging

logger = logging.getLogger(__name__)


class RLSManager:
    """
    Manages Row Level Security policies for multi-tenant Superset deployment
    """

    def __init__(self, app):
        self.app = app
        self.security_manager = app.appbuilder.sm

    def create_tenant_rls_rule(
        self, tenant_id: str, tenant_name: str, datasets: Optional[List[str]] = None
    ) -> Dict:
        """
        Create RLS rule for a specific tenant

        Args:
            tenant_id: UUID of the tenant
            tenant_name: Name of the tenant
            datasets: List of dataset names to apply RLS to (None = all)

        Returns:
            Dictionary with created rule information
        """
        try:
            from superset.models.core import Database
            from superset.connectors.sqla.models import SqlaTable
            from superset.security.manager import RLSRule

            # Get database
            database = self.security_manager.get_session.query(Database).first()

            if not database:
                logger.error("No database found")
                return {"error": "Database not found"}

            # Create RLS filter clause
            filter_clause = f"tenant_id = '{tenant_id}'"

            # Get datasets to apply RLS
            if datasets:
                dataset_objs = []
                for ds_name in datasets:
                    ds = (
                        self.security_manager.get_session.query(SqlaTable)
                        .filter(SqlaTable.table_name == ds_name)
                        .first()
                    )
                    if ds:
                        dataset_objs.append(ds)
            else:
                # Apply to all datasets
                dataset_objs = (
                    self.security_manager.get_session.query(SqlaTable)
                    .filter(SqlaTable.database_id == database.id)
                    .all()
                )

            created_rules = []

            for dataset in dataset_objs:
                # Check if rule already exists
                existing_rule = (
                    self.security_manager.get_session.query(RLSRule)
                    .filter(
                        RLSRule.name == f"tenant_{tenant_name}_{dataset.table_name}",
                        RLSRule.table_id == dataset.id,
                    )
                    .first()
                )

                if existing_rule:
                    logger.info(f"RLS rule already exists for {dataset.table_name}")
                    continue

                # Create new RLS rule
                rls_rule = RLSRule(
                    name=f"tenant_{tenant_name}_{dataset.table_name}",
                    filter_type="Regular",
                    tables=[dataset],
                    clause=filter_clause,
                    description=f"Tenant isolation for {tenant_name}",
                )

                self.security_manager.get_session.add(rls_rule)
                created_rules.append(
                    {
                        "rule_name": rls_rule.name,
                        "dataset": dataset.table_name,
                        "filter": filter_clause,
                    }
                )

            self.security_manager.get_session.commit()

            logger.info(
                f"Created {len(created_rules)} RLS rules for tenant {tenant_name}"
            )

            return {
                "tenant_id": tenant_id,
                "tenant_name": tenant_name,
                "rules_created": len(created_rules),
                "rules": created_rules,
            }

        except Exception as e:
            logger.error(f"Error creating RLS rules: {str(e)}")
            self.security_manager.get_session.rollback()
            return {"error": str(e)}

    def remove_tenant_rls_rules(self, tenant_name: str) -> bool:
        """
        Remove all RLS rules for a tenant

        Args:
            tenant_name: Name of the tenant

        Returns:
            True if successful
        """
        try:
            from superset.security.manager import RLSRule

            rules = (
                self.security_manager.get_session.query(RLSRule)
                .filter(RLSRule.name.like(f"tenant_{tenant_name}_%"))
                .all()
            )

            for rule in rules:
                self.security_manager.get_session.delete(rule)

            self.security_manager.get_session.commit()

            logger.info(f"Removed {len(rules)} RLS rules for tenant {tenant_name}")
            return True

        except Exception as e:
            logger.error(f"Error removing RLS rules: {str(e)}")
            self.security_manager.get_session.rollback()
            return False

    def list_tenant_rls_rules(self, tenant_name: Optional[str] = None) -> List[Dict]:
        """
        List all RLS rules, optionally filtered by tenant

        Args:
            tenant_name: Optional tenant name to filter by

        Returns:
            List of RLS rule dictionaries
        """
        try:
            from superset.security.manager import RLSRule

            query = self.security_manager.get_session.query(RLSRule)

            if tenant_name:
                query = query.filter(RLSRule.name.like(f"tenant_{tenant_name}_%"))

            rules = query.all()

            return [
                {
                    "id": rule.id,
                    "name": rule.name,
                    "filter_type": rule.filter_type,
                    "clause": rule.clause,
                    "tables": [t.table_name for t in rule.tables],
                    "description": rule.description,
                }
                for rule in rules
            ]

        except Exception as e:
            logger.error(f"Error listing RLS rules: {str(e)}")
            return []

    def update_tenant_rls_filter(
        self, tenant_id: str, tenant_name: str, new_filter: str
    ) -> bool:
        """
        Update the filter clause for all RLS rules of a tenant

        Args:
            tenant_id: UUID of the tenant
            tenant_name: Name of the tenant
            new_filter: New filter clause

        Returns:
            True if successful
        """
        try:
            from superset.security.manager import RLSRule

            rules = (
                self.security_manager.get_session.query(RLSRule)
                .filter(RLSRule.name.like(f"tenant_{tenant_name}_%"))
                .all()
            )

            for rule in rules:
                rule.clause = new_filter

            self.security_manager.get_session.commit()

            logger.info(f"Updated {len(rules)} RLS rules for tenant {tenant_name}")
            return True

        except Exception as e:
            logger.error(f"Error updating RLS rules: {str(e)}")
            self.security_manager.get_session.rollback()
            return False
