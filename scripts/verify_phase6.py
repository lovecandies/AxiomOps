import json
import time
from uuid import uuid4

import httpx

from axiom_ops.control_plane.config import ControlPlaneSettings
from axiom_ops.control_plane.database import Database
from axiom_ops.control_plane.models import (
    RcaDraft,
    VerificationDecision,
    VerificationResult,
)
from axiom_ops.control_plane.rca_repository import RcaRepository


def seed_verified_rca(
    database: Database,
    incident_id: str,
    evidence_ids: list[str],
) -> str:
    run_id = str(uuid4())
    repository = RcaRepository(database)
    repository.create_run(
        run_id=run_id,
        incident_id=incident_id,
        model="scripted-phase6-seed",
        graph_version="phase6-seed",
        evidence_ids=evidence_ids,
    )
    repository.finish_run(
        run_id=run_id,
        incident_id=incident_id,
        draft=RcaDraft(
            summary="Inventory fault is active and should be reset in sandbox.",
            root_cause="The inventory service has an injected active fault.",
            confidence=0.9,
            contributing_factors=["Order flow depends on inventory availability."],
            rejected_hypotheses=[],
            evidence_ids=evidence_ids,
            limitations=["This script seeds a deterministic RCA for Phase 6 recovery."],
        ),
        verification=VerificationResult(
            decision=VerificationDecision.APPROVED,
            rationale="Seeded RCA cites immutable Phase 3 Evidence for Phase 6 validation.",
        ),
        steps=[
            {
                "node_name": "phase6_seed",
                "role": "independent_verifier",
                "output": {"purpose": "phase6 recovery validation"},
            }
        ],
        model_calls=0,
        total_tokens=0,
        duration_ms=0,
    )
    return run_id


def main() -> int:
    settings = ControlPlaneSettings()
    database = Database(settings)
    with httpx.Client(timeout=10) as client:
        fault = client.post(
            "http://127.0.0.1:18002/admin/faults",
            json={"mode": "unavailable", "delay_ms": 0, "error_rate": 0.0},
        )
        fault.raise_for_status()
        time.sleep(2)

        incident = client.post(
            "http://127.0.0.1:18000/incidents",
            headers={"Idempotency-Key": f"phase6-{uuid4()}"},
            json={
                "title": "Inventory unavailable recovery",
                "service": "inventory-service",
                "severity": "SEV2",
                "summary": "Validate approval-gated sandbox recovery.",
            },
        )
        incident.raise_for_status()
        incident_id = incident.json()["id"]

        metric = client.post(
            f"http://127.0.0.1:18000/incidents/{incident_id}/tools/metrics",
            json={"signal": "inventory_active_fault"},
        )
        metric.raise_for_status()
        health = client.post(
            f"http://127.0.0.1:18000/incidents/{incident_id}/tools/health",
            json={"service": "inventory-service"},
        )
        health.raise_for_status()
        evidence_ids = [metric.json()["id"], health.json()["id"]]
        run_id = seed_verified_rca(database, incident_id, evidence_ids)

        approval = client.post(
            f"http://127.0.0.1:18000/incidents/{incident_id}/recovery-approvals",
            headers={
                "X-AxiomOps-User": "phase6-commander",
                "X-AxiomOps-Role": "commander",
            },
            json={
                "run_id": run_id,
                "action": "reset_inventory_fault",
                "reason": "Verified RCA identified an active inventory fault.",
            },
        )
        approval.raise_for_status()
        approval_id = approval.json()["id"]

        blocked = client.post(
            f"http://127.0.0.1:18000/recovery-approvals/{approval_id}/approve",
            headers={
                "X-AxiomOps-User": "phase6-commander",
                "X-AxiomOps-Role": "approver",
            },
            json={"comment": "self approval should be blocked"},
        )
        if blocked.status_code != 403:
            raise RuntimeError("self approval was not blocked")

        approved = client.post(
            f"http://127.0.0.1:18000/recovery-approvals/{approval_id}/approve",
            headers={
                "X-AxiomOps-User": "phase6-approver",
                "X-AxiomOps-Role": "approver",
            },
            json={"comment": "approved for sandbox recovery"},
        )
        approved.raise_for_status()

        execution = client.post(
            f"http://127.0.0.1:18000/recovery-approvals/{approval_id}/execute",
            headers={
                "X-AxiomOps-User": "phase6-operator",
                "X-AxiomOps-Role": "operator",
            },
        )
        execution.raise_for_status()
        result = execution.json()
        if result["status"] != "SUCCEEDED":
            raise RuntimeError(f"recovery did not succeed: {result}")
        if result["before_state"]["mode"] != "unavailable":
            raise RuntimeError("recovery did not capture pre-action fault state")
        if result["verification"]["passed"] is not True:
            raise RuntimeError("post-recovery verification did not pass")

        repeated = client.post(
            f"http://127.0.0.1:18000/recovery-approvals/{approval_id}/execute",
            headers={
                "X-AxiomOps-User": "phase6-operator",
                "X-AxiomOps-Role": "operator",
            },
        )
        repeated.raise_for_status()
        if repeated.json()["id"] != result["id"]:
            raise RuntimeError("recovery execution was not idempotent")

        current_fault = client.get("http://127.0.0.1:18002/admin/faults")
        current_fault.raise_for_status()
        if current_fault.json()["mode"] != "none":
            raise RuntimeError("inventory fault was not reset")

    print(
        json.dumps(
            {
                "passed": True,
                "incident_id": incident_id,
                "run_id": run_id,
                "approval_id": approval_id,
                "execution_id": result["id"],
                "execution_status": result["status"],
                "self_approval_status": blocked.status_code,
                "before_state": result["before_state"],
                "verification": result["verification"],
                "idempotent_execute": True,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
