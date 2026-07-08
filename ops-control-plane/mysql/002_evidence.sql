CREATE TABLE IF NOT EXISTS evidence (
    id CHAR(36) PRIMARY KEY,
    incident_id CHAR(36) NOT NULL,
    kind VARCHAR(32) NOT NULL,
    tool_name VARCHAR(128) NOT NULL,
    tool_input JSON NOT NULL,
    source VARCHAR(512) NOT NULL,
    artifact_path VARCHAR(512) NOT NULL,
    content_sha256 CHAR(64) NOT NULL,
    byte_size BIGINT UNSIGNED NOT NULL,
    observed_at DATETIME(6) NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT fk_evidence_incident
        FOREIGN KEY (incident_id) REFERENCES incidents(id),
    CONSTRAINT uq_evidence_artifact_path UNIQUE (artifact_path),
    CONSTRAINT chk_evidence_kind CHECK (
        kind IN ('METRIC_SNAPSHOT', 'SERVICE_HEALTH')
    ),
    INDEX idx_evidence_incident (incident_id, created_at, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

DROP TRIGGER IF EXISTS evidence_prevent_update;
DROP TRIGGER IF EXISTS evidence_prevent_delete;

DELIMITER //
CREATE TRIGGER evidence_prevent_update
BEFORE UPDATE ON evidence
FOR EACH ROW
BEGIN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'evidence is immutable';
END//

CREATE TRIGGER evidence_prevent_delete
BEFORE DELETE ON evidence
FOR EACH ROW
BEGIN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'evidence is immutable';
END//
DELIMITER ;
