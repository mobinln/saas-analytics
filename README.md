# Multi-Tenant SaaS Analytics Platform

A production-ready, multi-tenant analytics platform built with modern data engineering tools. This platform ingests product usage events from thousands of customers, ensures complete tenant data isolation, and provides embedded analytics dashboards with row-level security.

## 🏗️ Architecture

```
┌─────────────────┐
│  SaaS Product   │
│   (Customers)   │
└────────┬────────┘
         │ Events
         ▼
┌─────────────────┐
│     Kafka       │◄───── Event Producer (Simulator)
│  Event Stream   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Airflow      │
│  Orchestration  │
├─────────────────┤
│ • Event Ingest  │
│ • dbt Transform │
│ • Provisioning  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐       ┌─────────────────┐
│   PostgreSQL    │◄──────┤      dbt        │
│  Data Warehouse │       │  Transformations│
│   + RLS Policies│       │   + Metrics     │
└────────┬────────┘       └─────────────────┘
         │
         ▼
┌─────────────────┐       ┌─────────────────┐
│  Apache Superset│◄──────┤   API Service   │
│  BI + Dashboards│       │ Tenant Provision│
│   + Guest Token │       │  + Guest Tokens │
└─────────────────┘       └─────────────────┘
         │
         ▼
┌─────────────────┐
│   Customers     │
│ Embedded Dashboards
└─────────────────┘
```

## 🎯 Key Features

### Multi-Tenancy & Security

- **Row-Level Security (RLS)**: Complete data isolation at PostgreSQL level
- **dbt Tenant Filtering**: Consistent tenant context across transformations
- **Superset RLS**: Dashboard-level tenant isolation
- **Guest Tokens**: Secure, time-limited embedded analytics access

### Data Pipeline

- **Real-time Ingestion**: Kafka for event streaming
- **Orchestration**: Airflow for pipeline management
- **Transformations**: dbt for data modeling with version control
- **Materialized Views**: Query result caching for performance

### Analytics

- **Embedded Dashboards**: Superset with guest token authentication
- **Usage Metrics**: Pre-aggregated tenant usage analytics
- **Cost Attribution**: Per-tenant query cost tracking
- **API Access**: RESTful API for tenant management

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- 8GB+ RAM recommended
- Ports available: 5432, 8080, 8088, 8000, 9092

### 1. Clone and Setup

```bash
# Clone the repository
git clone <repo-url>
cd mt-analytics-platform

# Start all services
docker-compose up -d

# Wait for services to be healthy (2-3 minutes)
docker-compose ps
```

### 2. Access Services

| Service        | URL                        | Credentials                     |
| -------------- | -------------------------- | ------------------------------- |
| **Airflow**    | http://localhost:8080      | admin / admin                   |
| **Superset**   | http://localhost:8088      | admin / admin                   |
| **API**        | http://localhost:8000/docs | N/A (OpenAPI)                   |
| **PostgreSQL** | localhost:5432             | analytics_user / analytics_pass |

### 3. Verify Setup

```bash
# Check Airflow DAGs are loaded
curl http://localhost:8080/api/v1/dags

# Check API health
curl http://localhost:8000/health

# List tenants
curl http://localhost:8000/api/v1/tenants
```

## 📊 Component Details

### PostgreSQL (Data Warehouse)

- **Port**: 5432
- **Database**: analytics_db
- **Schemas**:
  - `raw`: Event data from Kafka
  - `staging`: Cleaned staging models
  - `analytics`: Analytics-ready marts
- **RLS**: Enabled on all tenant-scoped tables

### Kafka (Event Streaming)

- **Port**: 9092 (internal), 29092 (host)
- **Topic**: `tenant_events`
- **Event Producer**: Simulates realistic SaaS usage events
- **Retention**: 7 days default

### Airflow (Orchestration)

- **Port**: 8080
- **Executor**: CeleryExecutor with Redis
- **DAGs**:
  - `event_ingestion`: Kafka → PostgreSQL (every 5 minutes)
  - `dbt_transformation`: Run dbt models (hourly)
  - `tenant_provisioning`: New tenant setup (on-demand)

### dbt (Transformations)

- **Version**: 1.8.7
- **Profiles**: Development & Production
- **Models**:
  - **Staging**: `stg_events`, `stg_tenants`
  - **Intermediate**: `int_tenant_events_filtered`
  - **Marts**: `fct_usage_events`, `dim_tenants`
  - **Metrics**: `tenant_usage_metrics`
- **Tests**: Data quality and tenant isolation

### Apache Superset (BI)

- **Port**: 8088
- **Version**: 4.1.0
- **Features**:
  - Row-level security
  - Guest token authentication
  - Embedded dashboards
  - Query result caching

### API Service (FastAPI)

- **Port**: 8000
- **Documentation**: http://localhost:8000/docs
- **Endpoints**:
  - `POST /api/v1/tenants`: Create tenant
  - `GET /api/v1/tenants`: List tenants
  - `POST /api/v1/guest-token`: Generate dashboard token
  - `GET /api/v1/tenants/{id}/usage`: Usage metrics
  - `GET /api/v1/tenants/{id}/cost`: Cost attribution

## 🔧 Usage Examples

### Create a New Tenant

```bash
curl -X POST http://localhost:8000/api/v1/tenants \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_name": "acme_corp",
    "tier": "enterprise",
    "industry": "technology",
    "seats": 100
  }'
```

### Generate Guest Token for Embedded Dashboard

```bash
curl -X POST http://localhost:8000/api/v1/guest-token \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "11111111-1111-1111-1111-111111111111",
    "user_email": "user@acme.com",
    "dashboard_id": 1
  }'
```

### Query Tenant Usage Metrics

```bash
curl http://localhost:8000/api/v1/tenants/11111111-1111-1111-1111-111111111111/usage?days=7
```

### Run dbt Manually

```bash
docker exec -it mt_airflow_webserver bash
cd /opt/dbt
dbt run --models +marts
dbt test
```

## 🔐 Security Features

### Database-Level Security

```sql
-- RLS policy on events table
CREATE POLICY tenant_isolation_policy ON raw.events
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant_id', true)::UUID);

-- Set tenant context before queries
SELECT set_tenant_context('11111111-1111-1111-1111-111111111111');
```

### dbt Tenant Filtering

```sql
-- Macro: tenant_filter
{% macro tenant_filter(tenant_id_column) %}
    WHERE {{ tenant_id_column }} = '{{ var('current_tenant_id') }}'::UUID
{% endmacro %}
```

### Superset Guest Token

```python
# JWT payload with RLS rules
{
  "user": {"username": "user@acme.com"},
  "resources": [{"type": "dashboard", "id": "1"}],
  "rls": [{"clause": "tenant_id = '11111111-...'"}],
  "exp": 1234567890
}
```

## 📈 Monitoring & Operations

### Check Pipeline Health

```bash
# Airflow DAG status
docker exec mt_airflow_webserver airflow dags list

# Check last DAG runs
docker exec mt_airflow_webserver airflow dags list-runs -d event_ingestion

# View logs
docker-compose logs -f airflow_worker
```

### Monitor Event Ingestion

```bash
# PostgreSQL event count
docker exec mt_postgres psql -U analytics_user -d analytics_db \
  -c "SELECT tenant_id, COUNT(*) FROM raw.events GROUP BY tenant_id;"

# Kafka consumer lag
docker exec mt_kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --group airflow_ingestion \
  --describe
```

### Cost Attribution

```bash
# Query tenant costs
curl http://localhost:8000/api/v1/tenants/11111111-1111-1111-1111-111111111111/cost?days=30
```

## 🧪 Testing

### Test Tenant Isolation

```bash
# Run dbt tests
docker exec mt_airflow_webserver bash -c "cd /opt/dbt && dbt test"

# Manual verification
docker exec mt_postgres psql -U superset_user -d analytics_db \
  -c "SELECT set_tenant_context('11111111-1111-1111-1111-111111111111');
      SELECT COUNT(*) FROM raw.events;"
```

### Load Testing

```bash
# Adjust event volume
docker-compose exec event_producer bash
export EVENTS_PER_BATCH=1000
python producer.py
```

## 🔄 Data Flow

1. **Event Generation**: Event producer simulates SaaS product usage
2. **Streaming**: Events published to Kafka topic `tenant_events`
3. **Ingestion**: Airflow DAG consumes Kafka and loads to PostgreSQL `raw.events`
4. **Transformation**: dbt models transform raw data into analytics marts
5. **Aggregation**: Materialized views cache common queries
6. **Visualization**: Superset dashboards with RLS filters
7. **Embedding**: Guest tokens for secure dashboard embedding

## 🛠️ Development

### Add New Event Type

1. Update `event-producer/producer.py` event types
2. Add to dbt variable in `dbt_project.yml`
3. Update staging model `stg_events.sql`
4. Run `dbt run --models stg_events+`

### Create New Metric

1. Add SQL model to `dbt/models/marts/metrics/`
2. Reference in `tenant_usage_metrics.sql`
3. Run `dbt run --models metrics`
4. Create Superset chart

### Add Tenant-Specific Dashboard

1. Create dashboard in Superset UI
2. Configure RLS rules via API
3. Generate guest token with dashboard ID
4. Embed in customer portal

## 📝 Configuration

### Environment Variables

```bash
# PostgreSQL
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_USER=analytics_user
POSTGRES_PASSWORD=analytics_pass
POSTGRES_DB=analytics_db

# Kafka
KAFKA_BOOTSTRAP_SERVERS=kafka:9092

# Superset
SUPERSET_SECRET_KEY=change_me
SUPERSET_URL=http://superset:8088

# Airflow
AIRFLOW__CORE__EXECUTOR=CeleryExecutor
AIRFLOW__CORE__FERNET_KEY=your_fernet_key
```

### Scale Configuration

- **Workers**: Increase `airflow_worker` replicas
- **Kafka Partitions**: Increase for parallel processing
- **PostgreSQL**: Configure connection pooling
- **Superset**: Enable Redis for caching

## 🚨 Troubleshooting

### Services Won't Start

```bash
# Check logs
docker-compose logs -f

# Restart specific service
docker-compose restart airflow_webserver

# Clean restart
docker-compose down -v
docker-compose up -d
```

### Airflow DAGs Not Running

```bash
# Check DAG status
docker exec mt_airflow_webserver airflow dags list

# Unpause DAG
docker exec mt_airflow_webserver airflow dags unpause event_ingestion

# Trigger manually
docker exec mt_airflow_webserver airflow dags trigger event_ingestion
```

### Superset Connection Issues

```bash
# Test database connection
docker exec mt_superset superset db upgrade

# Recreate admin
docker exec mt_superset superset fab create-admin \
  --username admin --password admin \
  --firstname Admin --lastname User \
  --email admin@example.com
```

## 📚 Additional Resources

- [dbt Documentation](https://docs.getdbt.com)
- [Apache Airflow Docs](https://airflow.apache.org/docs)
- [Superset Documentation](https://superset.apache.org/docs/intro)
- [Kafka Documentation](https://kafka.apache.org/documentation)

## 🤝 Contributing

This is a demonstration project. For production use:

1. Implement proper authentication/authorization
2. Add SSL/TLS for all connections
3. Configure production-grade PostgreSQL
4. Set up monitoring (Prometheus, Grafana)
5. Implement backup/recovery procedures
6. Add rate limiting and DDoS protection
7. Configure proper logging aggregation

## 📄 License

MIT License - See LICENSE file for details

---

**Note**: This platform is configured for development/demonstration. Production deployment requires additional security hardening, scalability tuning, and operational monitoring.
