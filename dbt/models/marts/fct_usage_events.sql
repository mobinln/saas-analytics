{{
    config(
        materialized='incremental',
        unique_key='event_id',
        on_schema_change='fail',
        tags=['marts', 'facts'],
        indexes=[
            {'columns': ['tenant_id'], 'type': 'btree'},
            {'columns': ['event_date'], 'type': 'btree'},
            {'columns': ['tenant_id', 'event_date'], 'type': 'btree'}
        ]
    )
}}

-- Fact table: Usage events with tenant isolation
-- This is the primary fact table for analytics

SELECT
    event_id,
    tenant_id,
    tenant_name,
    tier,
    industry,
    event_type,
    event_timestamp,
    event_date,
    event_hour,
    day_of_week,
    hour_of_day,
    user_id,
    session_id,
    page_url,
    referrer,
    device_type,
    browser,
    country,
    event_sequence_in_session,
    events_in_session,
    session_duration_minutes,
    is_session_start,
    ingested_at,
    
    -- Cost attribution metadata
    tier_level,
    
    -- Surrogate key for partitioning
    {{ dbt_utils.generate_surrogate_key(['event_id']) }} as event_sk

FROM {{ ref('int_tenant_events_filtered') }}

{% if is_incremental() %}
    WHERE event_timestamp > (SELECT MAX(event_timestamp) FROM {{ this }})
{% endif %}