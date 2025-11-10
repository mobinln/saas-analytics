{{
    config(
        materialized='table',
        tags=['marts', 'dimensions']
    )
}}

-- Dimension table: Tenants
-- Slowly changing dimension type 1 (overwrite)

SELECT
    tenant_id,
    tenant_name,
    created_at,
    updated_at,
    status,
    tier,
    tier_level,
    industry,
    seats,
    subscription_start,
    days_since_created,
    
    -- Categorizations
    CASE
        WHEN tier = 'enterprise' THEN 'High Value'
        WHEN tier = 'premium' THEN 'Medium Value'
        ELSE 'Standard Value'
    END AS value_segment,
    
    CASE
        WHEN days_since_created <= 30 THEN 'New'
        WHEN days_since_created <= 90 THEN 'Growing'
        WHEN days_since_created <= 365 THEN 'Established'
        ELSE 'Mature'
    END AS lifecycle_stage,
    
    -- Surrogate key
    {{ dbt_utils.generate_surrogate_key(['tenant_id']) }} as tenant_sk

FROM {{ ref('stg_tenants') }}