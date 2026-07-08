import json
import sys
import time
from uuid import uuid4

import httpx


def main() -> int:
    idempotency_key = f"phase2-{uuid4()}"
    payload = {
        "title": "Inventory latency detected",
        "service": "inventory-service",
        "severity": "SEV2",
        "summary": "p95 latency exceeded the experiment threshold",
    }
    with httpx.Client(base_url="http://127.0.0.1:18000", timeout=5) as client:
        created = client.post(
            "/incidents",
            headers={"Idempotency-Key": idempotency_key},
            json=payload,
        )
        created.raise_for_status()
        repeated = client.post(
            "/incidents",
            headers={"Idempotency-Key": idempotency_key},
            json=payload,
        )
        repeated.raise_for_status()
        incident_id = created.json()["id"]
        if created.status_code != 201 or repeated.status_code != 200:
            raise RuntimeError("idempotent create status codes did not match")
        if repeated.json()["id"] != incident_id:
            raise RuntimeError("idempotent replay created another incident")

        deadline = time.monotonic() + 45
        incident = created.json()
        while time.monotonic() < deadline:
            response = client.get(f"/incidents/{incident_id}")
            response.raise_for_status()
            incident = response.json()
            if (
                incident["status"] == "INVESTIGATION_QUEUED"
                and incident["outbox"][0]["status"] == "PUBLISHED"
            ):
                break
            time.sleep(1)
        else:
            raise RuntimeError("incident did not reach the queued state")

    result = {
        "passed": True,
        "incident_id": incident_id,
        "idempotent_replay": True,
        "status": incident["status"],
        "outbox_status": incident["outbox"][0]["status"],
        "outbox_attempts": incident["outbox"][0]["attempts"],
        "event_types": [event["event_type"] for event in incident["events"]],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"phase2 verification failed: {exc}", file=sys.stderr)
        raise
