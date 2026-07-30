"""Run a real-model first-round diagnostic planner evaluation."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv

from axiom_ops.control_plane.config import ControlPlaneSettings
from axiom_ops.control_plane.models import DiagnosticToolName
from axiom_ops.control_plane.rca_model import DeepSeekRcaModel


ROOT = Path(__file__).resolve().parents[1]
TOOLS = {item.value for item in DiagnosticToolName}
CASES = [
    ("unavailable", "Inventory returns 503; confirm the active dependency fault.", {"health"}, "fault_state"),
    ("order-impact", "Orders are reported failing; verify user-visible downstream impact.", {"fault_state"}, "order_flow"),
    ("latency", "Order requests are slow while the dependency is reachable; quantify the anomaly.", {"health", "order_flow"}, "metrics"),
    ("trace-gap", "Metrics show downstream failures but the failing hop is unknown.", {"metrics", "fault_state"}, "trace"),
    ("change-correlation", "Failures started after a suspected inventory update; inspect recent changes.", {"metrics", "health", "order_flow"}, "change"),
    ("health-gap", "The order path is failing but inventory reachability has not been checked.", {"fault_state", "order_flow", "metrics"}, "health"),
    ("fault-gap", "The order path and metrics are abnormal; confirm whether an active fault exists.", {"order_flow", "metrics", "health"}, "fault_state"),
    ("order-gap", "Inventory is unhealthy; verify the customer-facing order path.", {"fault_state", "health", "metrics"}, "order_flow"),
    ("trace-latency", "Latency is elevated without a trace of the order-to-inventory call.", {"metrics", "health", "fault_state", "order_flow"}, "trace"),
]


def main() -> None:
    load_dotenv(ROOT / ".env", override=True)
    os.environ.setdefault(
        "AXIOMOPS_CONTROL_DEEPSEEK_API_KEY", os.getenv("DEEPSEEK_API_KEY", "")
    )
    os.environ.setdefault(
        "AXIOMOPS_CONTROL_DEEPSEEK_MODEL", os.getenv("DEEPSEEK_MODEL", "")
    )
    model = DeepSeekRcaModel(ControlPlaneSettings())
    results = []
    for case_id, summary, existing, expected in CASES:
        catalog = [
            {"id": f"{case_id}-{tool}", "kind": tool.upper(), "source": "planner-evaluation"}
            for tool in sorted(existing)
        ]
        try:
            proposal = model.plan_tools(
                {"id": case_id, "title": case_id, "service": "inventory-service", "severity": "SEV2", "summary": summary},
                catalog,
            )
            selected = []
            rejected = 0
            for item in proposal.selections:
                tool = item.tool.value
                if tool not in TOOLS or tool in existing or tool in selected or len(selected) >= 2:
                    rejected += 1
                else:
                    selected.append(tool)
            status = "model"
        except Exception as exc:
            selected = []
            rejected = 0
            status = f"error:{type(exc).__name__}"
        baseline_calls = len(TOOLS - existing)
        results.append({
            "case_id": case_id,
            "existing_tools": sorted(existing),
            "expected_tool": expected,
            "baseline_missing_only_calls": baseline_calls,
            "model_selected_tools": selected,
            "rejected_proposals": rejected,
            "required_tool_selected": expected in selected,
            "status": status,
        })
    successful = [item for item in results if item["status"] == "model"]
    report = {
        "schema_version": 1,
        "evaluation": "real-model-controlled-planner-first-round",
        "generated_at": datetime.now(UTC).isoformat(),
        "model": model.model_name,
        "case_count": len(results),
        "metrics": {
            "model_success_rate": round(len(successful) / len(results), 4),
            "required_first_tool_coverage": round(sum(item["required_tool_selected"] for item in results) / len(results), 4),
            "baseline_missing_only_tool_calls": sum(item["baseline_missing_only_calls"] for item in results),
            "planner_tool_calls": sum(len(item["model_selected_tools"]) for item in results),
            "planner_tool_call_reduction_rate": round(1 - sum(len(item["model_selected_tools"]) for item in results) / sum(item["baseline_missing_only_calls"] for item in results), 4),
            "rejected_proposal_count": sum(item["rejected_proposals"] for item in results),
        },
        "results": results,
    }
    output = ROOT / "artifacts" / "evaluations" / f"tool-planner-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(output), **report}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
