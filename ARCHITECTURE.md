# Multi-Tenant SaaS Analytics Platform - Architecture

## Overview

This platform implements a production-grade, multi-tenant analytics system that processes usage events from thousands of customers while ensuring complete data isolation and providing embedded analytics dashboards.

## Core Architecture Principles

### 1. Multi-Tenancy

- **Database-level isolation**: PostgreSQL Row-Level Security (RLS)
- **Transformation-level filtering**: dbt macros for consistent tenant context
- **Dashboard-level security**: Superset RLS rules and guest tokens
- **API-level validation**: Tenant context in all operations

### 2. Data Flow

```
┌──────────────────────────────────────────────────────────────┐
│                     EVENT GENERATION                          │
│  SaaS Product Usage → Event Producer (Simulator)             │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│                    EVENT STREAMING                            │
│  Kafka Topic: tenant_events                                   │
│  - Partitioning by tenant_id                                  │
│  - Retention: 7 days                                          │
│  - Replication: 1 (configurable)                              │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│                    RAW DATA INGESTION                         │
│  Airflow DAG: event_ingestion (every 5 minutes)              │
│  - Kafka Consumer with offset management                      │
│  - Batch insert to PostgreSQL raw.events                      │
│  - Data quality validation                                    │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│                  DATA TRANSFORMATION                          │
│  Airflow DAG: dbt_transformation (hourly)                    │
│  - dbt staging models (cleaning)                              │
│  - dbt intermediate models (business logic)                   │
│  - dbt marts (analytics-ready)                                │
│  - dbt metrics (aggregations)                                 │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│                    ANALYTICS LAYER                            │
│  PostgreSQL Analytics Schema                                  │
│  - fct_usage_events (fact table)                              │
│  - dim_tenants (dimension)                                    │
│  - tenant_usage_metrics (metrics view)                        │
│  - Materialized views for caching                             │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│                  VISUALIZATION & ACCESS                       │
│  Apache Superset + API Service                                │
│  - Row-level security enforcement                             │
│  - Guest token generation (JWT)                               │
│  - Embedded dashboard URLs                                    │
│  - Query result caching                                       │
└──────────────────────────────────────────────────────────────┘
```

## Component Details

### PostgreSQL Data Warehouse

**Schemas:**

- `raw`: Source data from Kafka (with RLS)
- `staging`: dbt staging models
- `analytics`: Production-ready marts and metrics

**Key Tables:**

- `raw.tenants`: Master tenant registry
- `raw.events`: All usage events with RLS policies
- `analytics.fct_usage_events`: Incremental fact table
- `analytics.dim_tenants`: Tenant dimension (SCD Type 1)
- `analytics.tenant_usage_metrics`: Pre-aggregated metrics

**Security:**

```sql
-- RLS Policy
CREATE POLICY tenant_isolation_policy ON raw.events
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant_id', true)::UUID);

-- Usage
SELECT set_tenant_context('tenant-uuid');
SELECT * FROM raw.events;  -- Only returns tenant's data
```

**Indexes:**

- `tenant_id` (all tenant-scoped tables)
- `event_timestamp` + `partition_date` (time-based queries)
- Composite: `(tenant_id, partition_date)` (optimal filtering)

### Kafka Event Streaming

**Topic Configuration:**

- `tenant_events`: Main event stream
- Partitions: 3 (scalable to tenant count)
- Replication factor: 1 (increase for HA)
- Retention: 7 days

**Event Schema:**

```json
{
  "event_id": "uuid",
  "tenant_id": "uuid",
  "event_type": "page_view|button_click|...",
  "event_timestamp": "ISO8601",
  "user_id": "string",
  "session_id": "string",
  "event_data": {
    "page_url": "string",
    "device_type": "mobile|desktop|tablet",
    "browser": "string",
    "country": "string",
    ...
  }
}
```

### Airflow Orchestration

**Infrastructure:**

- Executor: CeleryExecutor (distributed task execution)
- Broker: Redis (message queue)
- Metadata DB: PostgreSQL (separate from warehouse)

**DAGs:**

1. **event_ingestion** (Every 5 minutes)

   - Consume from Kafka
   - Validate event schema
   - Batch insert to PostgreSQL
   - Refresh materialized views

2. **dbt_transformation** (Hourly)

   - Data quality checks
   - Run dbt models: staging → marts
   - Run dbt tests
   - Generate documentation

3. **tenant_provisioning** (On-demand)
   - Create tenant record
   - Set up RLS policies
   - Create Superset RLS rules
   - Run initial transformations
   - Send notification

### dbt Transformations

**Project Structure:**

```
models/
├── staging/
│   ├── stg_events.sql          # Clean raw events
│   └── stg_tenants.sql         # Clean tenant data
├── intermediate/
│   └── int_tenant_events_filtered.sql  # Apply tenant filter
└── marts/
    ├── fct_usage_events.sql    # Main fact table (incremental)
    ├── dim_tenants.sql         # Tenant dimension
    └── metrics/
        └── tenant_usage_metrics.sql  # Aggregated metrics
```

**Key Features:**

- Incremental models for large fact tables
- Tenant filtering macro for consistent isolation
- dbt tests for data quality
- Source freshness checks
- Documentation generation

**Materialization Strategy:**

- Staging: Views (fast, always fresh)
- Intermediate: Views (business logic layer)
- Facts: Incremental tables (efficient updates)
- Dimensions: Tables (full refresh)
- Metrics: Views (on-demand aggregation)

### Apache Superset

**Configuration:**

- Version: 4.1.0
- Database: PostgreSQL (same as warehouse)
- Authentication: Database + Guest Tokens

**Features:**

- Row-level security with tenant filters
- Guest token generation (JWT, 5-min expiry)
- Embedded dashboard support
- Query result caching
- Dashboard permissions

**Guest Token Flow:**

```python
# 1. Generate token via API
POST /api/v1/guest-token
{
  "tenant_id": "uuid",
  "user_email": "user@company.com",
  "dashboard_id": 1
}

# 2. Receive JWT with RLS rules
{
  "token": "eyJ...",
  "dashboard_url": "http://superset:8088/guest_token",
  "expires_in": 300
}

# 3. Embed in customer portal
<iframe src="dashboard_url?guest_token=token"></iframe>
```

### API Service (FastAPI)

**Endpoints:**

- `POST /api/v1/tenants`: Create tenant
- `GET /api/v1/tenants`: List tenants
- `GET /api/v1/tenants/{id}`: Get tenant
- `DELETE /api/v1/tenants/{id}`: Deactivate tenant
- `POST /api/v1/guest-token`: Generate dashboard token
- `GET /api/v1/tenants/{id}/usage`: Usage metrics
- `GET /api/v1/tenants/{id}/cost`: Cost attribution

**Features:**

- OpenAPI/Swagger documentation
- Pydantic validation
- Database connection pooling
- JWT token generation
- CORS support for embedding

## Security Implementation

### 1. Row-Level Security (RLS)

PostgreSQL RLS ensures data isolation at the database level:

```sql
-- Enable RLS
ALTER TABLE raw.events ENABLE ROW LEVEL SECURITY;

-- Create policy
CREATE POLICY tenant_isolation_policy ON raw.events
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant_id', true)::UUID);

-- Grant to Superset user
GRANT SELECT ON raw.events TO superset_user;
```

**Benefits:**

- Automatic enforcement (can't be bypassed)
- Works with all query types
- Minimal application code changes
- Performance: uses indexes effectively

### 2. dbt Tenant Filtering

Consistent tenant context in transformations:

```sql
-- Macro: tenant_filter
{% macro tenant_filter(tenant_id_column) %}
    WHERE {{ tenant_id_column }} = '{{ var('current_tenant_id') }}'::UUID
{% endmacro %}

-- Usage in models
SELECT * FROM {{ ref('stg_events') }}
{{ tenant_filter('tenant_id') }}
```

### 3. Superset RLS Rules

Dashboard-level tenant isolation:

```python
# RLS Rule Configuration
{
  "name": "tenant_acme_corp_fct_usage_events",
  "filter_type": "Regular",
  "clause": "tenant_id = '11111111-...'",
  "tables": ["fct_usage_events"],
  "description": "Tenant isolation for acme_corp"
}
```

### 4. Guest Token Authentication

Time-limited, secure dashboard access:

```python
# JWT Payload
{
  "user": {"username": "user@company.com"},
  "resources": [{"type": "dashboard", "id": "1"}],
  "rls": [{"clause": "tenant_id = 'uuid'"}],
  "iat": 1234567890,
  "exp": 1234568190,  # 5 minutes
  "aud": "superset"
}
```

## Performance Optimizations

### 1. Query Result Caching

**Materialized Views:**

```sql
CREATE MATERIALIZED VIEW analytics.tenant_daily_summary AS
SELECT
    tenant_id,
    DATE(event_timestamp) as event_date,
    event_type,
    COUNT(*) as event_count,
    COUNT(DISTINCT user_id) as unique_users
FROM raw.events
GROUP BY tenant_id, DATE(event_timestamp), event_type;

-- Refresh strategy: Incremental via Airflow
REFRESH MATERIALIZED VIEW CONCURRENTLY analytics.tenant_daily_summary;
```

**Benefits:**

- Pre-computed aggregations
- Fast dashboard load times
- Reduced compute on raw tables

### 2. Partitioning Strategy

**Time-based partitioning** (future enhancement):

```sql
-- Partition by month
CREATE TABLE raw.events_2024_01 PARTITION OF raw.events
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
```

### 3. Index Optimization

**Covering indexes:**

```sql
CREATE INDEX idx_events_tenant_date_type
    ON raw.events(tenant_id, partition_date, event_type)
    INCLUDE (user_id, session_id);
```

## Cost Attribution

### Query Logging

Track resource usage per tenant:

```sql
-- Log every query
INSERT INTO analytics.tenant_query_log (
    tenant_id, query_duration_ms, rows_scanned,
    estimated_cost
) VALUES (...);

-- Calculate tenant costs
SELECT
    tenant_id,
    SUM(estimated_cost) as total_cost,
    AVG(query_duration_ms) as avg_duration
FROM analytics.tenant_query_log
WHERE query_timestamp >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY tenant_id;
```

### Cost Estimation Formula

```python
def estimate_query_cost(rows_scanned, duration_ms, query_type):
    """
    Simple cost model:
    - Base cost: $0.000001 per row scanned
    - Time cost: $0.00001 per second
    - Query type multiplier
    """
    row_cost = rows_scanned * 0.000001
    time_cost = (duration_ms / 1000) * 0.00001
    multiplier = {'SELECT': 1.0, 'INSERT': 1.5, 'UPDATE': 2.0}

    return (row_cost + time_cost) * multiplier.get(query_type, 1.0)
```

## Scalability Considerations

### Horizontal Scaling

**Kafka:**

- Increase partitions (up to # of tenants)
- Add more brokers for HA
- Enable compression (gzip)

**Airflow:**

- Scale worker nodes horizontally
- Increase Celery concurrency
- Use Kubernetes executor for large deployments

**PostgreSQL:**

- Read replicas for analytics queries
- Connection pooling (PgBouncer)
- Partition large tables
- Consider Citus for sharding

**Superset:**

- Multiple web servers behind load balancer
- Redis for query result caching
- Async query execution

### Vertical Scaling

**Database:**

- Increase RAM for query cache
- Faster disk I/O (NVMe SSDs)
- More CPU cores for parallel queries

**Kafka:**

- More memory for buffer cache
- Faster network for throughput

## Monitoring & Observability

### Key Metrics

**Pipeline Health:**

- Events ingested per minute
- Kafka consumer lag
- Airflow DAG success rate
- dbt test failures

**Tenant Metrics:**

- Active tenants
- Events per tenant
- Query volume per tenant
- Dashboard access frequency

**Performance:**

- Query response time (p50, p95, p99)
- Cache hit rate
- Database connection pool usage
- Kafka broker throughput

### Alerting Rules

```yaml
- name: EventIngestionLag
  condition: kafka_consumer_lag > 1000
  severity: warning

- name: DbtTestsFailed
  condition: dbt_tests_failed > 0
  severity: critical

- name: HighQueryLatency
  condition: query_p95_latency > 5000ms
  severity: warning

- name: TenantDataMissing
  condition: tenant_event_count_24h == 0
  severity: warning
```

## Disaster Recovery

### Backup Strategy

**PostgreSQL:**

- Daily full backups
- Continuous WAL archiving
- Point-in-time recovery capability
- Retention: 30 days

**Kafka:**

- Mirror cluster for critical topics
- Backup to S3/object storage
- Retention: 7 days minimum

### Recovery Procedures

**Data Loss:**

1. Stop event ingestion
2. Restore from latest backup
3. Replay Kafka messages (if within retention)
4. Verify data integrity
5. Resume ingestion

**Service Outage:**

1. Check service health endpoints
2. Review logs for errors
3. Restart affected services
4. Verify RLS policies intact
5. Test tenant isolation

## Future Enhancements

### Short Term

- [ ] Real-time streaming with Kafka Streams
- [ ] Incremental dbt model optimization
- [ ] Advanced cost attribution models
- [ ] Multi-region deployment

### Medium Term

- [ ] Machine learning models for usage prediction
- [ ] Anomaly detection per tenant
- [ ] Self-service analytics UI
- [ ] Advanced data quality monitoring

### Long Term

- [ ] Real-time OLAP with ClickHouse/Druid
- [ ] Data lake integration (Parquet on S3)
- [ ] GraphQL API for flexible queries
- [ ] AI-powered insights generation

## Development Workflow

### Local Development

```bash
# Start services
docker-compose up -d

# Make changes to dbt models
vim dbt/models/marts/my_new_model.sql

# Test locally
docker exec mt_airflow_webserver bash -c "cd /opt/dbt && dbt run --models my_new_model"

# Run tests
docker exec mt_airflow_webserver bash -c "cd /opt/dbt && dbt test"

# Check in Superset
# Access: http://localhost:8088
```

### CI/CD Pipeline

```yaml
# Example GitHub Actions workflow
name: Deploy Analytics Platform

on: [push]

jobs:
  test:
    - run: docker-compose up -d
    - run: python scripts/test_tenant_isolation.py
    - run: dbt test

  deploy:
    - run: terraform apply
    - run: dbt run --target prod
    - run: airflow dags trigger dbt_transformation
```

## Conclusion

This architecture provides:

- ✅ Complete tenant data isolation
- ✅ Scalable event processing pipeline
- ✅ Real-time analytics capabilities
- ✅ Secure embedded dashboard access
- ✅ Cost attribution per tenant
- ✅ Production-grade orchestration

The platform is built with modern data engineering best practices and can scale from hundreds to thousands of tenants while maintaining security and performance.
