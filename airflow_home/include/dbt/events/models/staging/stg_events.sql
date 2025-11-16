-- Staging: Clean and type raw events
{{ config(materialized='view') }}

SELECT
    event_id,
    tenant_id,
    user_id,
    event_type,
    event_timestamp::timestamp as event_timestamp,
    event_data->>'session_id' as session_id,
    event_data->>'page_url' as page_url,
    (event_data->>'duration_seconds')::int as duration_seconds,
    event_data->>'device' as device,
    event_data->>'browser' as browser,
    event_data->>'feature_name' as feature_name,
    event_data->>'status' as status
FROM {{ source('raw', 'tenant_events_raw') }}
WHERE event_timestamp >= CURRENT_DATE - INTERVAL '90 days'  -- Keep last 90 days