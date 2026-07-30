"""Render a Phase 12 report from reviewed Agent outcome records."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from axiom_ops.evaluation.agent_safety_report import build_agent_safety_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the Phase 12 Agent safety report.")
    parser.add_argument("input", type=Path, help="JSON array of reviewed evaluation cases")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    cases = json.loads(args.input.read_text(encoding="utf-8-sig"))
    report = build_agent_safety_report(cases)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
