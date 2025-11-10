{{
    config(
        materialized='view',
        tags=['staging', 'tenants']
    )
}}

SELECT
    tenant_id,
    tenant_name,
    created_at,
    updated_at,
    status,
    tier,
    metadata,
    
    -- Extract metadata fields
    (metadata->>'industry')::VARCHAR AS industry,
    (metadata->>'seats')::INTEGER AS seats,
    (metadata->>'subscription_start')::DATE AS subscription_start,
    
    -- Derived fields
    CURRENT_DATE - DATE(created_at) AS days_since_created,
    
    -- Tier categorization
    CASE tier
        WHEN 'enterprise' THEN 3
        WHEN 'premium' THEN 2
        WHEN 'standard' THEN 1
        ELSE 0
    END AS tier_level

FROM {{ source('raw', 'tenants') }}
WHERE status = 'active'