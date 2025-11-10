-- Enable RLS on analytics tables
ALTER TABLE analytics.fct_daily_usage ENABLE ROW LEVEL SECURITY;
ALTER TABLE analytics.fct_tenant_summary ENABLE ROW LEVEL SECURITY;

-- Create a role for each tenant (in practice, do this programmatically)
-- For demo, create a few tenant roles
DO $$
DECLARE
    tenant_rec RECORD;
BEGIN
    FOR tenant_rec IN SELECT tenant_id FROM dim_tenants LOOP
        EXECUTE format('CREATE ROLE %I LOGIN PASSWORD %L', 
                      tenant_rec.tenant_id, 
                      'secure_password_' || tenant_rec.tenant_id);
        
        -- Grant read access to analytics schema
        EXECUTE format('GRANT USAGE ON SCHEMA analytics TO %I', tenant_rec.tenant_id);
        EXECUTE format('GRANT SELECT ON ALL TABLES IN SCHEMA analytics TO %I', tenant_rec.tenant_id);
    END LOOP;
END $$;

-- Create RLS policies
CREATE POLICY tenant_isolation_daily ON analytics.fct_daily_usage
    FOR SELECT
    USING (tenant_id = current_user);

CREATE POLICY tenant_isolation_summary ON analytics.fct_tenant_summary
    FOR SELECT
    USING (tenant_id = current_user);

-- Create a service account that can see all tenants (for admin dashboards)
CREATE ROLE admin_viewer LOGIN PASSWORD 'admin_secure_pass';
GRANT USAGE ON SCHEMA analytics TO admin_viewer;
GRANT SELECT ON ALL TABLES IN SCHEMA analytics TO admin_viewer;

-- Admin bypass RLS
CREATE POLICY admin_all_access_daily ON analytics.fct_daily_usage
    FOR SELECT
    TO admin_viewer
    USING (true);

CREATE POLICY admin_all_access_summary ON analytics.fct_tenant_summary
    FOR SELECT
    TO admin_viewer
    USING (true);