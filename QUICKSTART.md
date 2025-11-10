# Quick Start Guide - Multi-Tenant Analytics Platform

## 🚀 Get Started in 5 Minutes

### Prerequisites

```bash
# Check you have the required tools
docker --version    # Docker 20.10+
docker-compose --version  # Docker Compose 1.29+

# Ensure ports are available
# 5432 (PostgreSQL), 8080 (Airflow), 8088 (Superset),
# 8000 (API), 9092 (Kafka)
```

### Installation

```bash
# 1. Create project directory
mkdir mt-analytics-platform
cd mt-analytics-platform

# 2. Copy all files from the artifact structure

# 3. Make scripts executable
chmod +x scripts/setup_all.sh
chmod +x scripts/test_tenant_isolation.py

# 4. Run complete setup
./scripts/setup_all.sh
```

The setup script will:

- ✅ Start all Docker services
- ✅ Wait for health checks
- ✅ Configure Airflow connections
- ✅ Install dbt packages
- ✅ Run initial transformations
- ✅ Generate sample data
- ✅ Verify the pipeline

**Expected time: 3-5 minutes**

### Verify Installation

```bash
# Check all services are running
docker-compose ps

# Should see:
# - postgres (healthy)
# - kafka (healthy)
# - airflow_webserver (healthy)
# - superset (running)
# - api (running)
# - event_producer (running)

# Run test suite
python3 scripts/test_tenant_isolation.py
```

## 📊 Access the Platform

### Airflow (Orchestration)

- URL: http://localhost:8080
- User: `admin`
- Pass: `admin`

**Try this:**

1. View DAGs list
2. Check "event_ingestion" DAG runs
3. Trigger "dbt_transformation" manually

### Superset (Analytics)

- URL: http://localhost:8088
- User: `admin`
- Pass: `admin`

**Try this:**

1. Go to Data → Databases
2. Add connection to PostgreSQL analytics schema
3. Create a simple chart from `tenant_usage_metrics`

### API Documentation

- URL: http://localhost:8000/docs
- Interactive Swagger UI

**Try this:**

```bash
# List all tenants
curl http://localhost:8000/api/v1/tenants | jq

# Get tenant usage
curl "http://localhost:8000/api/v1/tenants/11111111-1111-1111-1111-111111111111/usage?days=7" | jq
```

### PostgreSQL

```bash
# Connect via psql
docker exec -it mt_postgres psql -U analytics_user -d analytics_db

# Run some queries
SELECT COUNT(*) FROM raw.events;
SELECT tenant_name, COUNT(*) FROM raw.events e
  JOIN raw.tenants t ON e.tenant_id = t.tenant_id
  GROUP BY tenant_name;
```

## 🎯 Common Tasks

### Create a New Tenant

```bash
curl -X POST http://localhost:8000/api/v1/tenants \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_name": "my_company",
    "tier": "premium",
    "industry": "technology",
    "seats": 50
  }'
```

### Generate Guest Token (Embedded Analytics)

```bash
curl -X POST http://localhost:8000/api/v1/guest-token \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "11111111-1111-1111-1111-111111111111",
    "user_email": "user@mycompany.com",
    "dashboard_id": 1
  }' | jq
```

### View Tenant Data Isolation

```bash
# Connect as analytics user
docker exec -it mt_postgres psql -U analytics_user -d analytics_db

# Set tenant context and query
SELECT set_tenant_context('11111111-1111-1111-1111-111111111111');
SELECT COUNT(*) FROM raw.events;  -- Only this tenant's data

# Change tenant
SELECT set_tenant_context('22222222-2222-2222-2222-222222222222');
SELECT COUNT(*) FROM raw.events;  -- Different count!
```

### Run dbt Transformations

```bash
# Run all models
docker exec mt_airflow_webserver bash -c "cd /opt/dbt && dbt run --profiles-dir ."

# Run specific model
docker exec mt_airflow_webserver bash -c "cd /opt/dbt && dbt run --models fct_usage_events --profiles-dir ."

# Run tests
docker exec mt_airflow_webserver bash -c "cd /opt/dbt && dbt test --profiles-dir ."

# Generate docs
docker exec mt_airflow_webserver bash -c "cd /opt/dbt && dbt docs generate --profiles-dir ."
```

### Monitor Event Flow

```bash
# Check Kafka topic
docker exec mt_kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic tenant_events \
  --from-beginning \
  --max-messages 10

# Check event counts
docker exec mt_postgres psql -U analytics_user -d analytics_db \
  -c "SELECT
        tenant_id,
        COUNT(*) as events,
        MAX(event_timestamp) as latest_event
      FROM raw.events
      GROUP BY tenant_id;"

# Check Airflow logs
docker-compose logs -f airflow_worker
```

### Adjust Event Generation

```bash
# Stop current producer
docker-compose stop event_producer

# Modify environment and restart
docker-compose up -d event_producer \
  -e EVENTS_PER_BATCH=500 \
  -e BATCH_INTERVAL=5
```

## 🔧 Troubleshooting

### Services Won't Start

```bash
# Check logs
docker-compose logs --tail=50

# Check specific service
docker-compose logs airflow_webserver

# Restart everything
docker-compose down
docker-compose up -d

# Nuclear option (clears data)
docker-compose down -v
./scripts/setup_all.sh
```

### No Events in Database

```bash
# Check event producer is running
docker-compose ps event_producer

# Check Kafka has messages
docker exec mt_kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic tenant_events \
  --from-beginning \
  --max-messages 1

# Manually trigger ingestion DAG
docker exec mt_airflow_webserver \
  airflow dags trigger event_ingestion
```

### Airflow DAGs Not Running

```bash
# Check DAG list
docker exec mt_airflow_webserver airflow dags list

# Check for errors
docker exec mt_airflow_webserver airflow dags list-import-errors

# Unpause DAG
docker exec mt_airflow_webserver \
  airflow dags unpause event_ingestion

# Check scheduler logs
docker-compose logs airflow_scheduler
```

### dbt Tests Failing

```bash
# Run tests with verbose output
docker exec mt_airflow_webserver bash -c \
  "cd /opt/dbt && dbt test --profiles-dir . --debug"

# Check specific model
docker exec mt_airflow_webserver bash -c \
  "cd /opt/dbt && dbt run --models stg_events --profiles-dir ."

# Validate SQL
docker exec mt_airflow_webserver bash -c \
  "cd /opt/dbt && dbt compile --profiles-dir ."
```

## 📈 Next Steps

### 1. Create Your First Dashboard

1. Open Superset: http://localhost:8088
2. Create SQL Lab query:

```sql
SELECT
    event_date,
    total_events,
    unique_users,
    engagement_score
FROM analytics.tenant_usage_metrics
WHERE tenant_id = '11111111-1111-1111-1111-111111111111'
ORDER BY event_date DESC
LIMIT 30;
```

3. Save as dataset
4. Create chart (Line chart)
5. Add to new dashboard

### 2. Implement Custom Event Types

1. Edit `event-producer/producer.py`
2. Add new event type:

```python
EVENT_TYPES = [
    ('page_view', 0.40),
    ('button_click', 0.25),
    ('my_custom_event', 0.10),  # Add this
    ...
]
```

3. Restart producer:

```bash
docker-compose restart event_producer
```

### 3. Create Custom dbt Model

1. Create new file: `dbt/models/marts/custom_metric.sql`

```sql
SELECT
    tenant_id,
    DATE(event_timestamp) as metric_date,
    COUNT(*) as custom_count
FROM {{ ref('fct_usage_events') }}
WHERE event_type = 'my_custom_event'
GROUP BY 1, 2
```

2. Run the model:

```bash
docker exec mt_airflow_webserver bash -c \
  "cd /opt/dbt && dbt run --models custom_metric --profiles-dir ."
```

### 4. Set Up Production Deployment

1. Review `ARCHITECTURE.md` for scaling considerations
2. Update security keys in `.env`
3. Configure production database
4. Set up monitoring (Prometheus/Grafana)
5. Implement backup procedures
6. Configure SSL/TLS
7. Set up CI/CD pipeline

## 📚 Learning Resources

### Platform Components

- [dbt Documentation](https://docs.getdbt.com)
- [Apache Airflow](https://airflow.apache.org/docs)
- [Apache Superset](https://superset.apache.org/docs)
- [Apache Kafka](https://kafka.apache.org/documentation)
- [PostgreSQL RLS](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)

### Tutorials in This Repo

- `README.md` - Full platform documentation
- `ARCHITECTURE.md` - Detailed architecture guide
- `scripts/test_tenant_isolation.py` - Test suite examples

### Example Queries

**Find most active tenants:**

```sql
SELECT
    t.tenant_name,
    COUNT(*) as total_events,
    COUNT(DISTINCT e.user_id) as unique_users
FROM raw.events e
JOIN raw.tenants t ON e.tenant_id = t.tenant_id
GROUP BY t.tenant_name
ORDER BY total_events DESC;
```

**Daily event trends:**

```sql
SELECT
    DATE(event_timestamp) as date,
    event_type,
    COUNT(*) as count
FROM raw.events
WHERE event_timestamp >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY 1, 2
ORDER BY 1 DESC, 3 DESC;
```

**Cost by tenant:**

```sql
SELECT
    tenant_id,
    SUM(estimated_cost) as total_cost,
    COUNT(*) as query_count,
    AVG(query_duration_ms) as avg_duration
FROM analytics.tenant_query_log
WHERE query_timestamp >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY tenant_id
ORDER BY total_cost DESC;
```

## 🎓 Understanding the Platform

### Data Flow

1. **Events** generated by SaaS product (simulated)
2. **Kafka** streams events in real-time
3. **Airflow** orchestrates ingestion every 5 minutes
4. **PostgreSQL** stores raw events with RLS
5. **dbt** transforms data hourly
6. **Superset** visualizes with tenant isolation
7. **API** provides programmatic access

### Multi-Tenancy Layers

1. **Database RLS**: PostgreSQL policies
2. **dbt Macros**: Transformation filters
3. **Superset RLS**: Dashboard rules
4. **Guest Tokens**: JWT with tenant context

### Key Concepts

- **Tenant ID**: UUID identifying each customer
- **RLS Policy**: Database-level row filtering
- **Guest Token**: Time-limited dashboard access
- **Materialized View**: Pre-computed cache
- **Incremental Model**: Efficient dbt updates

## 💡 Tips

- **Performance**: Monitor query execution plans with `EXPLAIN ANALYZE`
- **Security**: Always use RLS, never trust application-level filtering alone
- **Costs**: Track per-tenant resource usage for accurate billing
- **Testing**: Run isolation tests after any schema changes
- **Monitoring**: Set up alerts for DAG failures and data quality issues

## 🆘 Get Help

```bash
# Check service health
curl http://localhost:8000/health
curl http://localhost:8080/health
curl http://localhost:8088/health

# View all logs
docker-compose logs -f

# Access container shell
docker exec -it mt_airflow_webserver bash
docker exec -it mt_postgres bash

# Run test suite
python3 scripts/test_tenant_isolation.py
```

---

**Ready to build?** Start with the examples above and explore the full documentation in `README.md` and `ARCHITECTURE.md`! 🚀
