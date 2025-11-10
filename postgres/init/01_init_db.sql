-- Initialize Multi-Tenant Analytics Database
-- ============================================

-- Create schemas
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS analytics;

-- Create tenants table
CREATE TABLE IF NOT EXISTS raw.tenants (
    tenant_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_name VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50) DEFAULT 'active',
    tier VARCHAR(50) DEFAULT 'standard', -- standard, premium, enterprise
    metadata JSONB
);

-- Create raw events table (from Kafka)
CREATE TABLE IF NOT EXISTS raw.events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES raw.tenants(tenant_id),
    event_type VARCHAR(100) NOT NULL,
    event_timestamp TIMESTAMP NOT NULL,
    user_id VARCHAR(255),
    session_id VARCHAR(255),
    event_data JSONB,
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    partition_date DATE GENERATED ALWAYS AS (DATE(event_timestamp)) STORED
);

-- Create indexes for performance
CREATE INDEX idx_events_tenant_id ON raw.events(tenant_id);
CREATE INDEX idx_events_event_type ON raw.events(event_type);
CREATE INDEX idx_events_timestamp ON raw.events(event_timestamp);
CREATE INDEX idx_events_partition_date ON raw.events(partition_date);
CREATE INDEX idx_events_tenant_partition ON raw.events(tenant_id, partition_date);

-- Create tenant access log for cost attribution
CREATE TABLE IF NOT EXISTS analytics.tenant_query_log (
    log_id BIGSERIAL PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES raw.tenants(tenant_id),
    query_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    query_duration_ms INTEGER,
    rows_scanned INTEGER,
    query_type VARCHAR(100),
    dashboard_id INTEGER,
    estimated_cost DECIMAL(10, 4)
);

CREATE INDEX idx_query_log_tenant ON analytics.tenant_query_log(tenant_id);
CREATE INDEX idx_query_log_timestamp ON analytics.tenant_query_log(query_timestamp);

-- Seed some initial tenants
INSERT INTO raw.tenants (tenant_id, tenant_name, tier, metadata) VALUES
    ('11111111-1111-1111-1111-111111111111', 'acme_corp', 'enterprise', '{"industry": "technology", "seats": 100}'::jsonb),
    ('22222222-2222-2222-2222-222222222222', 'beta_inc', 'premium', '{"industry": "finance", "seats": 50}'::jsonb),
    ('33333333-3333-3333-3333-333333333333', 'gamma_ltd', 'standard', '{"industry": "retail", "seats": 10}'::jsonb)
ON CONFLICT (tenant_id) DO NOTHING;

-- Enable Row Level Security
ALTER TABLE raw.events ENABLE ROW LEVEL SECURITY;

-- Create RLS policy for tenant isolation
-- This will be managed by dbt but we set up the framework
CREATE POLICY tenant_isolation_policy ON raw.events
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant_id', true)::UUID);

-- Create a function to set tenant context
CREATE OR REPLACE FUNCTION set_tenant_context(p_tenant_id UUID)
RETURNS void AS $$
BEGIN
    PERFORM set_config('app.current_tenant_id', p_tenant_id::text, false);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Create application user for Superset with limited permissions
CREATE USER superset_user WITH PASSWORD 'superset_pass';
GRANT CONNECT ON DATABASE analytics_db TO superset_user;
GRANT USAGE ON SCHEMA raw, staging, analytics TO superset_user;
GRANT SELECT ON ALL TABLES IN SCHEMA raw, staging, analytics TO superset_user;
GRANT EXECUTE ON FUNCTION set_tenant_context(UUID) TO superset_user;

-- Grant future privileges
ALTER DEFAULT PRIVILEGES IN SCHEMA raw, staging, analytics
    GRANT SELECT ON TABLES TO superset_user;

-- Create materialized views for common aggregations (cache layer)
CREATE MATERIALIZED VIEW IF NOT EXISTS analytics.tenant_daily_summary AS
SELECT 
    tenant_id,
    DATE(event_timestamp) as event_date,
    event_type,
    COUNT(*) as event_count,
    COUNT(DISTINCT user_id) as unique_users,
    COUNT(DISTINCT session_id) as unique_sessions
FROM raw.events
GROUP BY tenant_id, DATE(event_timestamp), event_type;

CREATE UNIQUE INDEX idx_tenant_daily_summary_unique 
    ON analytics.tenant_daily_summary(tenant_id, event_date, event_type);

-- Create refresh function
CREATE OR REPLACE FUNCTION refresh_tenant_summary()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY analytics.tenant_daily_summary;
END;
$$ LANGUAGE plpgsql;

COMMENT ON TABLE raw.tenants IS 'Master table of all tenants in the system';
COMMENT ON TABLE raw.events IS 'Raw event data from Kafka with tenant isolation via RLS';
COMMENT ON TABLE analytics.tenant_query_log IS 'Query log for cost attribution per tenant';
COMMENT ON MATERIALIZED VIEW analytics.tenant_daily_summary IS 'Pre-aggregated daily metrics per tenant for performance';