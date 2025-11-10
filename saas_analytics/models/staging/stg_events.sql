-- Staging: Clean and type raw events
{{ config(materialized='view') }}

SELECT
    event_id,
    tenant_id,
    user_id,
    event_type,
    timestamp::timestamp as event_timestamp,
    properties->>'session_id' as session_id,
    properties->>'page_url' as page_url,
    (properties->>'duration_seconds')::int as duration_seconds,
    properties->>'device' as device,
    properties->>'browser' as browser,
    properties->>'feature_name' as feature_name,
    properties->>'status' as status,
    tenant_metadata->>'plan' as tenant_plan,
    ingested_at
FROM {{ source('raw', 'raw_events') }}
WHERE timestamp >= CURRENT_DATE - INTERVAL '90 days'  -- Keep last 90 days