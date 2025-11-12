# Analytics Platform

## Architecture Overview

```text

Event Sources → api.FastAPI → Kafka → api.event_consumer → PostgreSQL → Dagster → dbt → Superset

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
psql -h localhost -U analytics -d analytics_db

```

## Resources

- [dbt Quick Start](https://docs.getdbt.com/guides/manual-install?step=1)
- [dbt Documentation](https://docs.getdbt.com/)
- [Apache Kafka Documentation](https://kafka.apache.org/documentation/)
- [Apache Superset Documentation](https://superset.apache.org/docs/intro)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Dagster Quick Start](https://docs.dagster.io/getting-started/quickstart)
