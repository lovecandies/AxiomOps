CREATE TABLE incidents (
    id CHAR(36) PRIMARY KEY,
    idempotency_key VARCHAR(128) NOT NULL,
    request_fingerprint CHAR(64) NOT NULL,
    title VARCHAR(255) NOT NULL,
    service VARCHAR(128) NOT NULL,
    severity VARCHAR(16) NOT NULL,
    summary VARCHAR(2000) NOT NULL,
    status VARCHAR(32) NOT NULL,
    version INT UNSIGNED NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    CONSTRAINT uq_incidents_idempotency_key UNIQUE (idempotency_key),
    CONSTRAINT chk_incidents_status CHECK (
        status IN ('RECEIVED', 'INVESTIGATION_QUEUED')
    ),
    CONSTRAINT chk_incidents_severity CHECK (severity IN ('SEV1', 'SEV2', 'SEV3'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE incident_events (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    incident_id CHAR(36) NOT NULL,
    event_type VARCHAR(128) NOT NULL,
    from_status VARCHAR(32) NULL,
    to_status VARCHAR(32) NOT NULL,
    metadata JSON NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT fk_incident_events_incident
        FOREIGN KEY (incident_id) REFERENCES incidents(id),
    INDEX idx_incident_events_incident (incident_id, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE outbox_events (
    id CHAR(36) PRIMARY KEY,
    aggregate_type VARCHAR(64) NOT NULL,
    aggregate_id CHAR(36) NOT NULL,
    event_type VARCHAR(128) NOT NULL,
    payload JSON NOT NULL,
    status VARCHAR(16) NOT NULL,
    attempts INT UNSIGNED NOT NULL DEFAULT 0,
    available_at DATETIME(6) NOT NULL,
    locked_by VARCHAR(128) NULL,
    locked_at DATETIME(6) NULL,
    broker_message_id VARCHAR(128) NULL,
    last_error VARCHAR(2000) NULL,
    published_at DATETIME(6) NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    CONSTRAINT fk_outbox_incident
        FOREIGN KEY (aggregate_id) REFERENCES incidents(id),
    CONSTRAINT chk_outbox_status CHECK (status IN ('PENDING', 'SENDING', 'PUBLISHED')),
    INDEX idx_outbox_dispatch (status, available_at, locked_at, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE processed_messages (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    consumer_group VARCHAR(128) NOT NULL,
    event_id CHAR(36) NOT NULL,
    broker_message_id VARCHAR(128) NOT NULL,
    processed_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT uq_processed_group_event UNIQUE (consumer_group, event_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
