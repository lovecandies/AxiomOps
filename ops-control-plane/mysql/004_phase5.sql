CREATE TABLE IF NOT EXISTS agent_run_contexts (
    run_id CHAR(36) PRIMARY KEY,
    original_bytes BIGINT UNSIGNED NOT NULL,
    compressed_bytes BIGINT UNSIGNED NOT NULL,
    capsules JSON NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT fk_agent_run_contexts_run
        FOREIGN KEY (run_id) REFERENCES agent_runs(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

DROP TRIGGER IF EXISTS agent_run_contexts_prevent_update;
DROP TRIGGER IF EXISTS agent_run_contexts_prevent_delete;

DELIMITER //
CREATE TRIGGER agent_run_contexts_prevent_update
BEFORE UPDATE ON agent_run_contexts
FOR EACH ROW
BEGIN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'agent run context is immutable';
END//

CREATE TRIGGER agent_run_contexts_prevent_delete
BEFORE DELETE ON agent_run_contexts
FOR EACH ROW
BEGIN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'agent run context is immutable';
END//
DELIMITER ;
