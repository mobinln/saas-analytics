# Analytics Platform

## Overview

This platform implements a production-grade, multi-tenant analytics system that processes usage events from thousands of customers while ensuring complete data isolation and providing embedded analytics dashboards.

## Core Architecture Principles

### 1. Multi-Tenancy

- **Database-level isolation**: PostgreSQL Row-Level Security (RLS)
- **Transformation-level filtering**: dbt macros for consistent tenant context

### 2. Data Flow

```
┌──────────────────────────────────────────────────────────────┐
│                     EVENT GENERATION                         │
│  SaaS Product Usage → FastaApi Server                        │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│                    EVENT STREAMING                           │
│  Kafka Topic: tenant_events                                  │
│  - Partitioning by tenant_id                                 │
│  - Retention: 7 days                                         │
│  - Replication: 1 (configurable)                             │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│                    RAW DATA INGESTION                        │
│  Python Event Consumer  -> Postgres                          │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│                  DATA TRANSFORMATION                         │
│  Airflow DAG: dbt_transformation (hourly)                    │
│  - dbt staging models (cleaning)                             │
│  - dbt intermediate models (business logic)                  │
│  - dbt marts (analytics-ready)                               │
│  - dbt metrics (aggregations)                                │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│                    ANALYTICS LAYER                           │
│  PostgreSQL Analytics Schema                                 │
│  - fct_usage_events (fact table)                             │
│  - dim_tenants (dimension)                                   │
│  - tenant_usage_metrics (metrics view)                       │
│  - Materialized views for caching                            │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│                  VISUALIZATION & ACCESS                      │
│  Metabase                                                    │
└──────────────────────────────────────────────────────────────┘
```

## Commands

```bash

# Run Docker Compose
docker compose up -d

# Run FastApi
cd api
source ./.venv/bin/activate
python3 -m fastapi dev main.py

# Run Kafka Consumer
cd api
source ./.venv/bin/activate
python3 event_consumer.py

# Go inside psql shell
docker exec -it postgres psql -U analytics -d analytics_db

```

## Services

- zookeeper
- kafka
- postgres
- metabase

## Resources

- [dbt Quick Start](https://docs.getdbt.com/guides/manual-install?step=1)
- [dbt Documentation](https://docs.getdbt.com/)
- [Apache Kafka Documentation](https://kafka.apache.org/documentation/)
- [Apache Superset Documentation](https://superset.apache.org/docs/intro)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Dagster Quick Start](https://docs.dagster.io/getting-started/quickstart)
