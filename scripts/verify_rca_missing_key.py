import json
from uuid import uuid4

import httpx


def main() -> int:
    with httpx.Client(base_url="http://127.0.0.1:18000", timeout=15) as client:
        created = client.post(
            "/incidents",
            headers={"Idempotency-Key": f"rca-no-key-{uuid4()}"},
            json={
                "title": "DeepSeek failure audit",
                "service": "inventory-service",
                "severity": "SEV3",
                "summary": "Verify that an unavailable model fails closed",
            },
        )
        created.raise_for_status()
        incident_id = created.json()["id"]
        metric = client.post(
            f"/incidents/{incident_id}/tools/metrics",
            json={"signal": "order_duration_total"},
        )
        metric.raise_for_status()
        run_response = client.post(f"/incidents/{incident_id}/rca-runs")
        run_response.raise_for_status()
        run = run_response.json()
        report = client.get(f"/incidents/{incident_id}/rca")

    if run["status"] != "FAILED":
        raise RuntimeError(f"expected FAILED run, got {run['status']}")
    if "DEEPSEEK_API_KEY is not configured" not in run["error"]:
        raise RuntimeError(f"unexpected failure: {run['error']}")
    if report.status_code != 404:
        raise RuntimeError("a failed run must not create an RCA report")

    print(
        json.dumps(
            {
                "passed": True,
                "incident_id": incident_id,
                "run_id": run["id"],
                "status": run["status"],
                "error": run["error"],
                "report_status": report.status_code,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
