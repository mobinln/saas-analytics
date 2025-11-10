#!/bin/bash

# Start all services
docker compose up -d

# Initialize Airflow
docker compose exec airflow-webserver airflow db init
docker compose exec airflow-webserver airflow users create \
    --username admin --password admin \
    --firstname Admin --lastname User \
    --role Admin --email admin@example.com

# Initialize Superset
docker compose exec superset superset db upgrade
docker compose exec superset superset fab create-admin \
    --username admin --password admin \
    --firstname Admin --lastname User \
    --email admin@example.com
docker compose exec superset superset init