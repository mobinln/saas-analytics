{{
    config(
        materialized='view',
        tags=['intermediate', 'tenant-filtered']
    )
}}

-- This model demonstrates tenant isolation at the transformation layer
-- Uses macro for consistent tenant filtering across all models

WITH events AS (
    SELECT * FROM {{ ref('stg_events') }}
),

tenants AS (
    SELECT * FROM {{ ref('stg_tenants') }}
),

-- Apply tenant filter using macro
filtered_events AS (
    SELECT
        e.*,
        t.tenant_name,
        t.tier,
        t.industry,
        t.tier_level
    FROM events e
    INNER JOIN tenants t ON e.tenant_id = t.tenant_id
    {{ tenant_filter('e.tenant_id') }}
),

-- Add session-level aggregations
enriched_events AS (
    SELECT
        fe.*,
        
        -- Session metrics
        ROW_NUMBER() OVER (
            PARTITION BY tenant_id, session_id 
            ORDER BY event_timestamp
        ) AS event_sequence_in_session,
        
        COUNT(*) OVER (
            PARTITION BY tenant_id, session_id
        ) AS events_in_session,
        
        MIN(event_timestamp) OVER (
            PARTITION BY tenant_id, session_id
        ) AS session_start_time,
        
        MAX(event_timestamp) OVER (
            PARTITION BY tenant_id, session_id
        ) AS session_end_time
        
    FROM filtered_events fe
)

SELECT
    *,
    
    -- Calculate session duration in minutes
    EXTRACT(EPOCH FROM (session_end_time - session_start_time)) / 60.0 AS session_duration_minutes,
    
    -- Flag first event in session
    CASE WHEN event_sequence_in_session = 1 THEN TRUE ELSE FALSE END AS is_session_start
    
FROM enriched_events