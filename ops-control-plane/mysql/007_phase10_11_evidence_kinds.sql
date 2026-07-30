ALTER TABLE evidence DROP CHECK chk_evidence_kind;

ALTER TABLE evidence
    ADD CONSTRAINT chk_evidence_kind
    CHECK (kind IN (
        'METRIC_SNAPSHOT',
        'SERVICE_HEALTH',
        'FAULT_STATE',
        'ORDER_FLOW_PROBE',
        'TRACE_SNAPSHOT',
        'CHANGE_EVENT'
    ));
