{{
    config(
        materialized='view',
        tags=['staging', 'events']
    )
}}

WITH source_events AS (
    SELECT
        event_id,
        tenant_id,
        event_type,
        event_timestamp,
        user_id,
        session_id,
        event_data,
        ingested_at,
        partition_date
    FROM {{ source('raw', 'events') }}
    
    {% if is_incremental() %}
        WHERE ingested_at > (SELECT MAX(ingested_at) FROM {{ this }})
    {% endif %}
),

cleaned_events AS (
    SELECT
        event_id,
        tenant_id,
        LOWER(TRIM(event_type)) AS event_type,
        event_timestamp,
        NULLIF(TRIM(user_id), '') AS user_id,
        NULLIF(TRIM(session_id), '') AS session_id,
        event_data,
        ingested_at,
        partition_date,
        
        -- Extract common fields from event_data JSONB
        (event_data->>'page_url')::VARCHAR AS page_url,
        (event_data->>'referrer')::VARCHAR AS referrer,
        (event_data->>'device_type')::VARCHAR AS device_type,
        (event_data->>'browser')::VARCHAR AS browser,
        (event_data->>'country')::VARCHAR AS country,
        
        -- Data quality flags
        CASE
            WHEN event_timestamp IS NULL THEN TRUE
            WHEN event_timestamp > CURRENT_TIMESTAMP THEN TRUE
            WHEN event_timestamp < CURRENT_TIMESTAMP - INTERVAL '30 days' THEN TRUE
            ELSE FALSE
        END AS is_invalid_timestamp,
        
        CASE
            WHEN user_id IS NULL AND session_id IS NULL THEN TRUE
            ELSE FALSE
        END AS is_missing_identifiers
        
    FROM source_events
)

SELECT
    event_id,
    tenant_id,
    event_type,
    event_timestamp,
    user_id,
    session_id,
    event_data,
    ingested_at,
    partition_date,
    page_url,
    referrer,
    device_type,
    browser,
    country,
    is_invalid_timestamp,
    is_missing_identifiers,
    
    -- Derived fields
    DATE(event_timestamp) AS event_date,
    DATE_TRUNC('hour', event_timestamp) AS event_hour,
    EXTRACT(DOW FROM event_timestamp) AS day_of_week,
    EXTRACT(HOUR FROM event_timestamp) AS hour_of_day
    
FROM cleaned_events
WHERE NOT is_invalid_timestamp  -- Filter out invalid records