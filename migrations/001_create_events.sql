CREATE DATABASE IF NOT EXISTS events;

CREATE TABLE IF NOT EXISTS events.events
(
    event_time  DateTime64(3) DEFAULT now64(3),
    name        LowCardinality(String),
    type        LowCardinality(String),
    path        String,
    data        Map(String, String) DEFAULT map()
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_time)
ORDER BY (type, event_time)
TTL toDateTime(event_time) + INTERVAL 90 DAY
SETTINGS index_granularity = 8192;
