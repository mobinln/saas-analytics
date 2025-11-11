# Analytics Platform

## Architecture Overview

```text

Event Sources → FastAPI → Kafka → Kafka Connect → PostgreSQL → Dagster → dbt → Superset

```

## Commands

```bash

# Run Docker Compose
docker compose up -d

# Setup kafka connect
curl -X POST http://localhost:8083/connectors \
  -H "Content-Type: application/json" \
  -d @connector-config.json

# Verify connector status
curl http://localhost:8083/connectors/postgres-sink/status

# Run FastApi
cd api
source ./.venv/bin/activate
python3 -m fastapi dev main.py

```

## Resources

- [dbt Quick Start](https://docs.getdbt.com/guides/manual-install?step=1)
- [dbt Documentation](https://docs.getdbt.com/)
- [Apache Kafka Documentation](https://kafka.apache.org/documentation/)
- [Apache Superset Documentation](https://superset.apache.org/docs/intro)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Dagster Quick Start](https://docs.dagster.io/getting-started/quickstart)
