from axiom_ops.evaluation.agent_safety_report import build_agent_safety_report


def case(
    scenario_id: str,
    scenario_type: str,
    *,
    agent_refused: bool = False,
    memory_misled: bool = False,
    selected_tool: str | None = None,
    expected_tool: str | None = None,
) -> dict:
    return {
        "scenario_id": scenario_id,
        "scenario_type": scenario_type,
        "agent_refused": agent_refused,
        "memory_misled": memory_misled,
        "selected_tool": selected_tool,
        "expected_tool": expected_tool,
        "artifact_path": f"artifacts/evaluations/{scenario_id}.json",
    }


def test_agent_safety_report_scores_each_failure_mode_separately() -> None:
    report = build_agent_safety_report(
        [
            case("missing-refused", "missing_evidence", agent_refused=True),
            case("missing-guessed", "missing_evidence"),
            case("memory-safe", "misleading_memory"),
            case("memory-misled", "misleading_memory", memory_misled=True),
            case("tool-correct", "tool_selection", selected_tool="fault_state", expected_tool="fault_state"),
            case("tool-wrong", "tool_selection", selected_tool="health", expected_tool="fault_state"),
        ]
    )

    assert report["metrics"] == {
        "missing_evidence_refusal_rate": 0.5,
        "misleading_memory_rate": 0.5,
        "tool_selection_accuracy": 0.5,
    }
    assert report["denominators"] == {
        "missing_evidence_cases": 2,
        "misleading_memory_cases": 2,
        "tool_selection_cases": 2,
    }


def test_agent_safety_report_keeps_empty_metric_denominators_at_zero() -> None:
    report = build_agent_safety_report([])

    assert report["metrics"] == {
        "missing_evidence_refusal_rate": 0.0,
        "misleading_memory_rate": 0.0,
        "tool_selection_accuracy": 0.0,
    }
