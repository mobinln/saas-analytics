"""
Apache Superset Configuration
Configured for multi-tenant analytics with RLS and guest tokens
"""

import os
from flask_appbuilder.security.manager import AUTH_DB

# Security Configuration
SECRET_KEY = os.getenv("SUPERSET_SECRET_KEY", "change_this_secret_key_in_production")
GUEST_TOKEN_JWT_SECRET = SECRET_KEY
GUEST_TOKEN_JWT_ALGO = "HS256"
GUEST_TOKEN_JWT_EXP_SECONDS = 300  # 5 minutes

# Authentication
AUTH_TYPE = AUTH_DB
AUTH_USER_REGISTRATION = False

# Database Configuration
POSTGRES_USER = os.getenv("POSTGRES_USER", "analytics_user")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "analytics_pass")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "analytics_db")

# SQLAlchemy connection string
SQLALCHEMY_DATABASE_URI = f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

# Superset metadata DB (same as data warehouse for simplicity)
# In production, you'd want separate DBs
SQLALCHEMY_EXAMPLES_URI = SQLALCHEMY_DATABASE_URI

# Enable Row Level Security
ROW_LEVEL_SECURITY = True
ENABLE_ROW_LEVEL_SECURITY = True

# Enable guest token authentication for embedded analytics
GUEST_TOKEN_HEADER_NAME = "X-GuestToken"
GUEST_ROLE_NAME = "Gamma"  # Default role for guest users

# Feature flags
FEATURE_FLAGS = {
    "DASHBOARD_NATIVE_FILTERS": True,
    "DASHBOARD_CROSS_FILTERS": True,
    "DASHBOARD_RBAC": True,
    "EMBEDDED_SUPERSET": True,
    "ENABLE_TEMPLATE_PROCESSING": True,
    "DASHBOARD_FILTERS_EXPERIMENTAL": True,
    "ALERT_REPORTS": False,  # Disable for simplicity
}

# Cache configuration for query results
CACHE_CONFIG = {
    "CACHE_TYPE": "SimpleCache",
    "CACHE_DEFAULT_TIMEOUT": 300,
    "CACHE_KEY_PREFIX": "superset_",
}

DATA_CACHE_CONFIG = {
    "CACHE_TYPE": "SimpleCache",
    "CACHE_DEFAULT_TIMEOUT": 300,
    "CACHE_KEY_PREFIX": "superset_data_",
}

# Query result caching
RESULTS_BACKEND = None  # Can be configured with Redis for production

# Enable query cost estimation
ESTIMATE_QUERY_COST = True
QUERY_COST_FORMATTERS_BY_ENGINE = {"postgresql": lambda cost: f"Cost: {cost:.2f}"}

# Async query configuration
GLOBAL_ASYNC_QUERIES_TRANSPORT = "polling"
GLOBAL_ASYNC_QUERIES_POLLING_DELAY = 500

# CORS for embedded dashboards
ENABLE_CORS = True
CORS_OPTIONS = {
    "supports_credentials": True,
    "allow_headers": ["*"],
    "resources": ["*"],
    "origins": ["*"],
}

# Embedded dashboard configuration
EMBEDDED_SUPERSET = True
TALISMAN_ENABLED = False  # Disable for development

# Multi-tenancy settings
SQLLAB_CTAS_NO_LIMIT = True

# Logging
LOG_LEVEL = "INFO"
ENABLE_TIME_ROTATE = True

# WebDriver for dashboard thumbnails (optional)
THUMBNAIL_SELENIUM_USER = None

# SQL Lab settings
SQLLAB_TIMEOUT = 300
SQLLAB_ASYNC_TIME_LIMIT_SEC = 300
SQL_MAX_ROW = 10000

# Database connection pool settings
SQLALCHEMY_POOL_SIZE = 5
SQLALCHEMY_POOL_TIMEOUT = 300
SQLALCHEMY_MAX_OVERFLOW = 10

# Session configuration
PERMANENT_SESSION_LIFETIME = 1800  # 30 minutes

# Custom CSS
# CUSTOM_CSS = """
# .navbar { background-color: #1a1a2e !important; }
# """


# RLS Configuration - Applied at query time
# This integrates with our tenant context system
class RLSConfig:
    """Row Level Security Configuration"""

    @staticmethod
    def get_rls_filters(table_name=None):
        """
        Return RLS filters based on current user/tenant context
        This is called by Superset before executing queries
        """
        from flask import g

        # Get tenant ID from guest token or user attributes
        tenant_id = getattr(g, "tenant_id", None)

        if tenant_id:
            return [
                {"clause": f"tenant_id = '{tenant_id}'", "filter_type": "tenant_filter"}
            ]

        return []


# Custom RLS filter function
def get_rls_filter_for_dataset(dataset, tenant_id=None):
    """
    Generate RLS filter for a dataset based on tenant context
    """
    if tenant_id:
        return f"tenant_id = '{tenant_id}'"
    return None
