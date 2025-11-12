CREATE TABLE tenant_events_raw (
    event_id VARCHAR(255) PRIMARY KEY,
    tenant_id VARCHAR(255),
    event_type VARCHAR(50),
    event_timestamp TIMESTAMP,
    user_id VARCHAR(255),
    session_id VARCHAR(255),
    event_data JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_tenant_id ON tenant_events_raw(tenant_id);
CREATE INDEX idx_event_type ON tenant_events_raw(event_type);
CREATE INDEX idx_event_timestamp ON tenant_events_raw(event_timestamp);
CREATE INDEX idx_event_data ON tenant_events_raw USING gin(event_data);

CREATE DATABASE metabaseappdb;
