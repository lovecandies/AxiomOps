"""Prepare, but never recover, the deterministic Phase 8 browser demo."""

import json
import time
from uuid import uuid4

import httpx

from axiom_ops.control_plane.config import ControlPlaneSettings
from axiom_ops.control_plane.database import Database
from verify_phase6 import seed_verified_rca


def main() -> int:
    with httpx.Client(timeout=10) as client:
        client.post(
            "http://127.0.0.1:18002/admin/faults",
            json={"mode": "unavailable", "delay_ms": 0, "error_rate": 0.0},
        ).raise_for_status()
        time.sleep(1)
        incident = client.post(
            "http://127.0.0.1:18000/incidents",
            headers={"Idempotency-Key": f"phase8-{uuid4()}"},
            json={
                "title": "Inventory unavailable — console demo",
                "service": "inventory-service",
                "severity": "SEV2",
                "summary": "Prepared deterministic Incident for the Phase 8 UI demo.",
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

    run_id = seed_verified_rca(
        Database(ControlPlaneSettings()), incident_id, [metric.json()["id"], health.json()["id"]]
    )
    print(json.dumps({"passed": True, "incident_id": incident_id, "run_id": run_id}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
