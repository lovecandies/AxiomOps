import hashlib
import json
import time
from uuid import uuid4

import httpx


def canonical_sha256(content: dict) -> str:
    data = json.dumps(
        content,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    with httpx.Client(timeout=8) as client:
        client.get("http://127.0.0.1:18001/orders/evidence-demo").raise_for_status()
        time.sleep(2)

        created = client.post(
            "http://127.0.0.1:18000/incidents",
            headers={"Idempotency-Key": f"evidence-{uuid4()}"},
            json={
                "title": "Collect typed evidence",
                "service": "inventory-service",
                "severity": "SEV2",
                "summary": "verify immutable metrics and health observations",
            },
        )
        created.raise_for_status()
        incident_id = created.json()["id"]

        metric = client.post(
            f"http://127.0.0.1:18000/incidents/{incident_id}/tools/metrics",
            json={"signal": "order_duration_total"},
        )
        metric.raise_for_status()
        health = client.post(
            f"http://127.0.0.1:18000/incidents/{incident_id}/tools/health",
            json={"service": "inventory-service"},
        )
        health.raise_for_status()

        evidence = client.get(
            f"http://127.0.0.1:18000/incidents/{incident_id}/evidence"
        )
        evidence.raise_for_status()
        items = evidence.json()
        if len(items) != 2:
            raise RuntimeError(f"expected 2 evidence records, got {len(items)}")

        for item in items:
            content = client.get(
                f"http://127.0.0.1:18000/evidence/{item['id']}/content"
            )
            content.raise_for_status()
            if canonical_sha256(content.json()) != item["content_sha256"]:
                raise RuntimeError(f"hash mismatch for {item['id']}")

    result = {
        "passed": True,
        "incident_id": incident_id,
        "evidence_count": len(items),
        "evidence": [
            {
                "id": item["id"],
                "kind": item["kind"],
                "tool_name": item["tool_name"],
                "artifact_path": item["artifact_path"],
                "content_sha256": item["content_sha256"],
            }
            for item in items
        ],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
