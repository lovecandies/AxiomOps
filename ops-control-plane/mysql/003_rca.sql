CREATE TABLE IF NOT EXISTS agent_runs (
    id CHAR(36) PRIMARY KEY,
    incident_id CHAR(36) NOT NULL,
    status VARCHAR(16) NOT NULL,
    model VARCHAR(128) NOT NULL,
    graph_version VARCHAR(32) NOT NULL,
    evidence_ids JSON NOT NULL,
    verification JSON NULL,
    error VARCHAR(4000) NULL,
    model_calls INT UNSIGNED NOT NULL DEFAULT 0,
    total_tokens INT UNSIGNED NOT NULL DEFAULT 0,
    duration_ms BIGINT UNSIGNED NULL,
    started_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    completed_at DATETIME(6) NULL,
    CONSTRAINT fk_agent_runs_incident
        FOREIGN KEY (incident_id) REFERENCES incidents(id),
    CONSTRAINT chk_agent_run_status CHECK (
        status IN ('RUNNING', 'COMPLETED', 'REJECTED', 'FAILED')
    ),
    INDEX idx_agent_runs_incident (incident_id, started_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS agent_run_steps (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    run_id CHAR(36) NOT NULL,
    node_name VARCHAR(64) NOT NULL,
    role VARCHAR(64) NULL,
    output JSON NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT fk_agent_run_steps_run
        FOREIGN KEY (run_id) REFERENCES agent_runs(id),
    INDEX idx_agent_run_steps_run (run_id, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS rca_reports (
    id CHAR(36) PRIMARY KEY,
    run_id CHAR(36) NOT NULL,
    incident_id CHAR(36) NOT NULL,
    summary VARCHAR(2000) NOT NULL,
    root_cause VARCHAR(2000) NOT NULL,
    confidence DECIMAL(5,4) NOT NULL,
    contributing_factors JSON NOT NULL,
    rejected_hypotheses JSON NOT NULL,
    evidence_ids JSON NOT NULL,
    limitations JSON NOT NULL,
    verification JSON NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT uq_rca_reports_run UNIQUE (run_id),
    CONSTRAINT fk_rca_reports_run FOREIGN KEY (run_id) REFERENCES agent_runs(id),
    CONSTRAINT fk_rca_reports_incident FOREIGN KEY (incident_id) REFERENCES incidents(id),
    CONSTRAINT chk_rca_confidence CHECK (confidence >= 0 AND confidence <= 1),
    INDEX idx_rca_reports_incident (incident_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

DROP TRIGGER IF EXISTS rca_reports_prevent_update;
DROP TRIGGER IF EXISTS rca_reports_prevent_delete;

DELIMITER //
CREATE TRIGGER rca_reports_prevent_update
BEFORE UPDATE ON rca_reports
FOR EACH ROW
BEGIN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'rca report is immutable';
END//

CREATE TRIGGER rca_reports_prevent_delete
BEFORE DELETE ON rca_reports
FOR EACH ROW
BEGIN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'rca report is immutable';
END//
DELIMITER ;
