#!/bin/bash
# Multi-Tenant Analytics Platform - Complete Setup Script
# This script initializes and verifies all platform components

set -e  # Exit on error

echo "======================================"
echo "Multi-Tenant Analytics Platform Setup"
echo "======================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}→ $1${NC}"
}

# Check prerequisites
print_info "Checking prerequisites..."

if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    print_error "Docker Compose is not installed"
    exit 1
fi

print_success "Prerequisites met"
echo ""

# Stop existing services
print_info "Stopping existing services (if any)..."
docker-compose down -v 2>/dev/null || true
print_success "Cleaned up existing services"
echo ""

# Build and start services
print_info "Building and starting services..."
docker-compose up -d --build

print_success "Services started"
echo ""

# Wait for services to be healthy
print_info "Waiting for services to become healthy..."

wait_for_service() {
    local service=$1
    local max_attempts=60
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if docker-compose ps | grep $service | grep -q "healthy"; then
            print_success "$service is healthy"
            return 0
        fi
        echo -n "."
        sleep 2
        attempt=$((attempt + 1))
    done
    
    print_error "$service did not become healthy"
    return 1
}

# Wait for core services
wait_for_service "postgres"
wait_for_service "kafka"
wait_for_service "redis"
wait_for_service "airflow_webserver"

echo ""
print_success "Core services are healthy"
echo ""

# Wait for Superset (takes longer to initialize)
print_info "Waiting for Superset to initialize (this may take 2-3 minutes)..."
sleep 30

max_attempts=30
attempt=1
while [ $attempt -le $max_attempts ]; do
    if curl -s http://localhost:8088/health > /dev/null 2>&1; then
        print_success "Superset is ready"
        break
    fi
    echo -n "."
    sleep 5
    attempt=$((attempt + 1))
done

if [ $attempt -gt $max_attempts ]; then
    print_error "Superset did not become ready"
fi

echo ""

# Configure Airflow connections
print_info "Configuring Airflow connections..."

docker exec mt_airflow_webserver bash -c "
    airflow connections delete postgres_default 2>/dev/null || true
    airflow connections add postgres_default \
        --conn-type postgres \
        --conn-host postgres \
        --conn-port 5432 \
        --conn-login analytics_user \
        --conn-password analytics_pass \
        --conn-schema analytics_db
"

print_success "Airflow connections configured"
echo ""

# Unpause DAGs
print_info "Unpausing Airflow DAGs..."

docker exec mt_airflow_webserver bash -c "
    airflow dags unpause event_ingestion
    airflow dags unpause dbt_transformation
"

print_success "DAGs unpaused"
echo ""

# Install dbt packages
print_info "Installing dbt packages..."

docker exec mt_airflow_webserver bash -c "
    cd /opt/dbt && dbt deps --profiles-dir .
"

print_success "dbt packages installed"
echo ""

# Run initial dbt models
print_info "Running initial dbt transformations..."

docker exec mt_airflow_webserver bash -c "
    cd /opt/dbt && dbt run --profiles-dir . --models +marts
"

print_success "dbt models built"
echo ""

# Trigger initial event ingestion
print_info "Triggering initial event ingestion..."

docker exec mt_airflow_webserver bash -c "
    airflow dags trigger event_ingestion
"

print_success "Event ingestion triggered"
echo ""

# Wait for some events to be generated
print_info "Waiting for event producer to generate sample data (30 seconds)..."
sleep 30

# Verify data
print_info "Verifying data pipeline..."

event_count=$(docker exec mt_postgres psql -U analytics_user -d analytics_db -t -c "SELECT COUNT(*) FROM raw.events;")
event_count=$(echo $event_count | xargs)  # Trim whitespace

if [ "$event_count" -gt 0 ]; then
    print_success "Events ingested: $event_count rows"
else
    print_error "No events found in database"
fi

tenant_count=$(docker exec mt_postgres psql -U analytics_user -d analytics_db -t -c "SELECT COUNT(*) FROM raw.tenants WHERE status='active';")
tenant_count=$(echo $tenant_count | xargs)

print_success "Active tenants: $tenant_count"
echo ""

# Verify API
print_info "Verifying API service..."

if curl -s http://localhost:8000/health | grep -q "healthy"; then
    print_success "API service is healthy"
else
    print_error "API service is not responding"
fi

echo ""

# Print access information
echo "======================================"
echo "Setup Complete! 🎉"
echo "======================================"
echo ""
echo "Service Access:"
echo "---------------"
echo "Airflow UI:     http://localhost:8080"
echo "                Username: admin"
echo "                Password: admin"
echo ""
echo "Superset UI:    http://localhost:8088"
echo "                Username: admin"
echo "                Password: admin"
echo ""
echo "API Docs:       http://localhost:8000/docs"
echo ""
echo "PostgreSQL:     localhost:5432"
echo "                Database: analytics_db"
echo "                User: analytics_user"
echo "                Password: analytics_pass"
echo ""
echo "Kafka:          localhost:29092"
echo ""
echo "Quick Commands:"
echo "---------------"
echo "# List all tenants"
echo "curl http://localhost:8000/api/v1/tenants"
echo ""
echo "# Create new tenant"
echo 'curl -X POST http://localhost:8000/api/v1/tenants -H "Content-Type: application/json" -d '"'"'{"tenant_name":"test_company","tier":"premium"}'"'"
echo ""
echo "# Generate guest token"
echo 'curl -X POST http://localhost:8000/api/v1/guest-token -H "Content-Type: application/json" -d '"'"'{"tenant_id":"11111111-1111-1111-1111-111111111111","user_email":"user@test.com"}'"'"
echo ""
echo "# View event counts by tenant"
echo 'docker exec mt_postgres psql -U analytics_user -d analytics_db -c "SELECT tenant_id, COUNT(*) FROM raw.events GROUP BY tenant_id;"'
echo ""
echo "# Check Airflow DAGs"
echo "docker exec mt_airflow_webserver airflow dags list"
echo ""
echo "# View logs"
echo "docker-compose logs -f airflow_worker"
echo ""
echo "To stop all services:"
echo "docker-compose down"
echo ""
echo "To completely reset (including data):"
echo "docker-compose down -v"
echo "======================================"