-- Fact table: Daily usage metrics per tenant
{{ config(
    materialized='incremental',
    unique_key=['tenant_id', 'date']
) }}

WITH daily_metrics AS (
    SELECT
        tenant_id,
        DATE(event_timestamp) as date,
        COUNT(DISTINCT user_id) as active_users,
        COUNT(DISTINCT session_id) as total_sessions,
        COUNT(*) as total_events,
        COUNT(*) FILTER (WHERE event_type = 'feature_used') as feature_uses,
        COUNT(*) FILTER (WHERE event_type = 'api_call') as api_calls,
        COUNT(*) FILTER (WHERE status = 'error') as error_count,
        ROUND(AVG(duration_seconds), 2) as avg_session_duration,
        MAX(event_timestamp) as last_activity_at
    FROM {{ ref('stg_events') }}
    {% if is_incremental() %}
        WHERE DATE(event_timestamp) > (SELECT MAX(date) FROM {{ this }})
    {% endif %}
    GROUP BY tenant_id, DATE(event_timestamp)
)

SELECT
    tenant_id,
    date,
    active_users,
    total_sessions,
    total_events,
    feature_uses,
    api_calls,
    error_count,
    avg_session_duration,
    ROUND(100.0 * error_count / NULLIF(total_events, 0), 2) as error_rate,
    last_activity_at
FROM daily_metrics