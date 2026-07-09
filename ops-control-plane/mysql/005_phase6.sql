CREATE TABLE IF NOT EXISTS recovery_approvals (
    id CHAR(36) PRIMARY KEY,
    incident_id CHAR(36) NOT NULL,
    run_id CHAR(36) NOT NULL,
    action VARCHAR(64) NOT NULL,
    status VARCHAR(16) NOT NULL,
    reason VARCHAR(1000) NOT NULL,
    requested_by VARCHAR(128) NOT NULL,
    approved_by VARCHAR(128) NULL,
    approval_comment VARCHAR(1000) NULL,
    requested_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    approved_at DATETIME(6) NULL,
    CONSTRAINT fk_recovery_approvals_incident
        FOREIGN KEY (incident_id) REFERENCES incidents(id),
    CONSTRAINT fk_recovery_approvals_run
        FOREIGN KEY (run_id) REFERENCES agent_runs(id),
    CONSTRAINT chk_recovery_approval_action CHECK (
        action IN ('reset_inventory_fault')
    ),
    CONSTRAINT chk_recovery_approval_status CHECK (
        status IN ('PENDING', 'APPROVED')
    ),
    INDEX idx_recovery_approvals_incident (incident_id, requested_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS recovery_executions (
    id CHAR(36) PRIMARY KEY,
    approval_id CHAR(36) NOT NULL,
    action VARCHAR(64) NOT NULL,
    status VARCHAR(16) NOT NULL,
    executed_by VARCHAR(128) NOT NULL,
    sandbox BOOLEAN NOT NULL,
    before_state JSON NOT NULL,
    action_result JSON NOT NULL,
    verification JSON NOT NULL,
    rollback JSON NULL,
    error VARCHAR(4000) NULL,
    started_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    completed_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT uq_recovery_executions_approval UNIQUE (approval_id),
    CONSTRAINT fk_recovery_executions_approval
        FOREIGN KEY (approval_id) REFERENCES recovery_approvals(id),
    CONSTRAINT chk_recovery_execution_action CHECK (
        action IN ('reset_inventory_fault')
    ),
    CONSTRAINT chk_recovery_execution_status CHECK (
        status IN ('SUCCEEDED', 'FAILED', 'ROLLED_BACK')
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

DROP TRIGGER IF EXISTS recovery_executions_prevent_update;
DROP TRIGGER IF EXISTS recovery_executions_prevent_delete;

DELIMITER //
CREATE TRIGGER recovery_executions_prevent_update
BEFORE UPDATE ON recovery_executions
FOR EACH ROW
BEGIN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'recovery execution is immutable';
END//

CREATE TRIGGER recovery_executions_prevent_delete
BEFORE DELETE ON recovery_executions
FOR EACH ROW
BEGIN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'recovery execution is immutable';
END//
DELIMITER ;
