"""Run deterministic AxiomOps engineering optimization benchmarks."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from axiom_ops.evaluation.optimization_benchmark import build_optimization_report


def main() -> None:
    report = build_optimization_report()
    output = Path("artifacts/evaluations") / f"optimization-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(output), **report}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
