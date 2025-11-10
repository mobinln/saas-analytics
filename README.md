# Saas Analytics

```markdown
[Simulated SaaS App] → [Event Generator]
↓
[Kafka/Redpanda]
↓
[Stream Processor (Python)]
↓
[PostgreSQL (Raw Events)]
↓
[dbt (Transformations)]
↓
[PostgreSQL (Analytics Schema with RLS)]
↓
[Apache Superset (Dashboards)]
↓
[Tenant-Specific Embedded Views]
```

## Install Airflow

```bash
AIRFLOW_VERSION="3.1.1"
PYTHON_VERSION="$(python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
CONSTRAINT_URL="https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-${PYTHON_VERSION}.txt"

uv pip install "apache-airflow==${AIRFLOW_VERSION}" --constraint "${CONSTRAINT_URL}"
```
