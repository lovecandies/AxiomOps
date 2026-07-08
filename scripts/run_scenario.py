import argparse
import json
from pathlib import Path

from axiom_ops.lab.scenario_runner import run_scenario
from axiom_ops.lab.scenarios import load_scenario, load_scenarios


def main() -> int:
    parser = argparse.ArgumentParser(description="Run an AxiomOps lab scenario.")
    parser.add_argument("scenario", nargs="?", help="Scenario id, or omit with --all.")
    parser.add_argument("--all", action="store_true", help="Run every scenario.")
    parser.add_argument(
        "--scenario-dir",
        type=Path,
        default=Path("ops-lab/scenarios"),
    )
    parser.add_argument("--artifact-root", type=Path, default=Path("artifacts/lab"))
    args = parser.parse_args()

    if args.all == bool(args.scenario):
        parser.error("provide exactly one scenario id or --all")

    if args.all:
        scenarios = load_scenarios(args.scenario_dir)
    else:
        scenarios = [load_scenario(args.scenario_dir / f"{args.scenario}.json")]

    results = []
    for scenario in scenarios:
        _, result = run_scenario(scenario, args.artifact_root)
        results.append(result)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    return 0 if results and all(result["passed"] for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
