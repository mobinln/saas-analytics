FROM apache/superset:4.1.0

USER root

# Install PostgreSQL driver
RUN pip install --no-cache-dir psycopg2-binary==2.9.9

# Copy custom config
COPY superset_config.py /app/pythonpath/
COPY security /app/security

USER superset

# Initialize Superset
RUN superset db upgrade && \
    superset fab create-admin \
    --username admin \
    --firstname Superset \
    --lastname Admin \
    --email admin@superset.com \
    --password admin && \
    superset init