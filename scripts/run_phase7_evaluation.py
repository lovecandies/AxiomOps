import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from axiom_ops.evaluation.phase7_report import build_phase7_report
from axiom_ops.lab.scenario_runner import run_scenario
from axiom_ops.lab.scenarios import load_scenarios, write_json


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the Phase 7 fault-set and ablation evaluation."
    )
    parser.add_argument(
        "--scenario-dir",
        type=Path,
        default=Path("ops-lab/scenarios"),
    )
    parser.add_argument("--artifact-root", type=Path, default=Path("artifacts/lab"))
    parser.add_argument(
        "--report-root",
        type=Path,
        default=Path("artifacts/evaluations"),
    )
    args = parser.parse_args()

    scenarios = load_scenarios(args.scenario_dir)
    results = []
    for scenario in scenarios:
        _, result = run_scenario(scenario, args.artifact_root)
        results.append(result)

    report = build_phase7_report(results)
    report_id = f"phase7-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"
    report_path = args.report_root / f"{report_id}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(report_path, report)
    print(json.dumps({**report, "report_path": str(report_path)}, ensure_ascii=False, indent=2))
    return 0 if report["metrics"]["closed_loop_pass_rate"] == 1.0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
