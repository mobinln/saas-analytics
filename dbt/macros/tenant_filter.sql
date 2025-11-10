{% macro tenant_filter(tenant_id_column) %}
    {#
        Macro to apply consistent tenant filtering across all models
        This ensures tenant isolation at the transformation layer
        
        Usage: {{ tenant_filter('tenant_id') }}
        
        In production, this would integrate with the session-based tenant context
    #}
    
    {% if var('current_tenant_id', none) %}
        WHERE {{ tenant_id_column }} = '{{ var('current_tenant_id') }}'::UUID
    {% else %}
        -- If no tenant specified, apply no filter (admin/system view)
        -- In production, you'd typically always require a tenant context
    {% endif %}
    
{% endmacro %}


{% macro generate_rls_policy(table_name, schema_name='analytics') %}
    {#
        Macro to generate Row Level Security policies for a table
        This can be executed as a post-hook or in a separate operation
        
        Usage: {{ generate_rls_policy('fct_usage_events') }}
    #}
    
    {% set sql %}
        -- Enable RLS on the table
        ALTER TABLE {{ schema_name }}.{{ table_name }} ENABLE ROW LEVEL SECURITY;
        
        -- Drop existing policy if it exists
        DROP POLICY IF EXISTS tenant_isolation_{{ table_name }} ON {{ schema_name }}.{{ table_name }};
        
        -- Create RLS policy for tenant isolation
        CREATE POLICY tenant_isolation_{{ table_name }} ON {{ schema_name }}.{{ table_name }}
            FOR ALL
            USING (
                tenant_id = current_setting('app.current_tenant_id', true)::UUID
            );
        
        -- Grant access to superset user
        GRANT SELECT ON {{ schema_name }}.{{ table_name }} TO superset_user;
    {% endset %}
    
    {{ return(sql) }}
    
{% endmacro %}


{% macro get_tenant_context() %}
    {#
        Helper macro to get current tenant context
        Returns the current tenant ID from session variable
    #}
    current_setting('app.current_tenant_id', true)::UUID
{% endmacro %}