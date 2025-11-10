-- Current tenant health metrics
{{ config(materialized='table') }}

WITH last_30_days AS (
    SELECT
        tenant_id,
        SUM(active_users) as total_active_users,
        SUM(total_events) as total_events,
        AVG(error_rate) as avg_error_rate,
        MAX(last_activity_at) as last_seen_at,
        COUNT(DISTINCT date) as days_active
    FROM {{ ref('fct_daily_usage') }}
    WHERE date >= CURRENT_DATE - INTERVAL '30 days'
    GROUP BY tenant_id
),

tenant_enriched AS (
    SELECT
        t.tenant_id,
        t.tenant_name,
        t.plan,
        COALESCE(m.total_active_users, 0) as active_users_30d,
        COALESCE(m.total_events, 0) as events_30d,
        COALESCE(m.avg_error_rate, 0) as avg_error_rate_30d,
        m.last_seen_at,
        COALESCE(m.days_active, 0) as days_active_30d,
        CASE
            WHEN m.last_seen_at > CURRENT_TIMESTAMP - INTERVAL '24 hours' THEN 'active'
            WHEN m.last_seen_at > CURRENT_TIMESTAMP - INTERVAL '7 days' THEN 'at_risk'
            ELSE 'churned'
        END as health_status
    FROM {{ ref('dim_tenants') }} t
    LEFT JOIN last_30_days m ON t.tenant_id = m.tenant_id
)

SELECT * FROM tenant_enriched