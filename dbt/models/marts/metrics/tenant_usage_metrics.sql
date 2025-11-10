{{
    config(
        materialized='view',
        tags=['metrics', 'usage']
    )
}}

-- Aggregated metrics per tenant
-- This view powers the main analytics dashboards

WITH daily_metrics AS (
    SELECT
        tenant_id,
        tenant_name,
        tier,
        industry,
        event_date,
        
        -- Volume metrics
        COUNT(*) AS total_events,
        COUNT(DISTINCT user_id) AS unique_users,
        COUNT(DISTINCT session_id) AS unique_sessions,
        COUNT(DISTINCT CASE WHEN is_session_start THEN session_id END) AS new_sessions,
        
        -- Engagement metrics
        AVG(events_in_session) AS avg_events_per_session,
        AVG(NULLIF(session_duration_minutes, 0)) AS avg_session_duration_minutes,
        
        -- Event type breakdown
        COUNT(CASE WHEN event_type = 'page_view' THEN 1 END) AS page_views,
        COUNT(CASE WHEN event_type = 'button_click' THEN 1 END) AS button_clicks,
        COUNT(CASE WHEN event_type = 'form_submit' THEN 1 END) AS form_submits,
        COUNT(CASE WHEN event_type = 'api_call' THEN 1 END) AS api_calls,
        COUNT(CASE WHEN event_type = 'feature_usage' THEN 1 END) AS feature_uses,
        
        -- Device breakdown
        COUNT(CASE WHEN device_type = 'mobile' THEN 1 END) AS mobile_events,
        COUNT(CASE WHEN device_type = 'desktop' THEN 1 END) AS desktop_events,
        COUNT(CASE WHEN device_type = 'tablet' THEN 1 END) AS tablet_events,
        
        -- Time-based metrics
        COUNT(CASE WHEN hour_of_day BETWEEN 9 AND 17 THEN 1 END) AS business_hours_events,
        COUNT(CASE WHEN day_of_week IN (0, 6) THEN 1 END) AS weekend_events
        
    FROM {{ ref('fct_usage_events') }}
    WHERE event_date >= CURRENT_DATE - INTERVAL '30 days'
    GROUP BY 1, 2, 3, 4, 5
),

rolling_metrics AS (
    SELECT
        *,
        
        -- 7-day rolling averages
        AVG(total_events) OVER (
            PARTITION BY tenant_id 
            ORDER BY event_date 
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        ) AS rolling_7d_avg_events,
        
        AVG(unique_users) OVER (
            PARTITION BY tenant_id 
            ORDER BY event_date 
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        ) AS rolling_7d_avg_users,
        
        -- Month-to-date totals
        SUM(total_events) OVER (
            PARTITION BY tenant_id, DATE_TRUNC('month', event_date)
            ORDER BY event_date
        ) AS mtd_total_events,
        
        SUM(unique_users) OVER (
            PARTITION BY tenant_id, DATE_TRUNC('month', event_date)
            ORDER BY event_date
        ) AS mtd_unique_users
        
    FROM daily_metrics
)

SELECT
    *,
    
    -- Calculated KPIs
    ROUND(unique_users::NUMERIC / NULLIF(unique_sessions, 0), 2) AS users_per_session,
    ROUND(total_events::NUMERIC / NULLIF(unique_users, 0), 2) AS events_per_user,
    ROUND((page_views::NUMERIC / NULLIF(total_events, 0)) * 100, 1) AS page_view_pct,
    ROUND((mobile_events::NUMERIC / NULLIF(total_events, 0)) * 100, 1) AS mobile_usage_pct,
    
    -- Engagement score (normalized 0-100)
    LEAST(100, ROUND(
        (COALESCE(avg_session_duration_minutes, 0) * 10) +
        (COALESCE(avg_events_per_session, 0) * 5) +
        (COALESCE(unique_users, 0) * 0.1)
    )) AS engagement_score

FROM rolling_metrics
ORDER BY tenant_id, event_date DESC