import json
from pathlib import Path

from pydantic import BaseModel, Field

from axiom_ops.lab.faults import FaultMode


class FaultDefinition(BaseModel):
    mode: FaultMode
    delay_ms: int = Field(ge=0, le=10_000)
    error_rate: float = Field(ge=0.0, le=1.0)


class ExpectedObservation(BaseModel):
    statuses: list[int]
    minimum_average_latency_ms: float = Field(ge=0)


class ScenarioDefinition(BaseModel):
    scenario_id: str
    title: str
    affected_service: str
    root_cause: str
    fault: FaultDefinition
    request_count: int = Field(gt=0, le=100)
    expected: ExpectedObservation
    allowed_actions: list[str]
    success_condition: str


def load_scenario(path: Path) -> ScenarioDefinition:
    return ScenarioDefinition.model_validate_json(path.read_text(encoding="utf-8"))


def load_scenarios(directory: Path) -> list[ScenarioDefinition]:
    return [load_scenario(path) for path in sorted(directory.glob("*.json"))]


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
