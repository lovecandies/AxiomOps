import json

import httpx
import pytest

from axiom_ops.control_plane.config import ControlPlaneSettings
from axiom_ops.control_plane.models import InvestigatorRole
from axiom_ops.control_plane.rca_model import DeepSeekRcaModel, RcaModelError


def plan_payload() -> dict:
    return {
        "tasks": [
            {
                "task_id": "metrics",
                "role": "metrics_investigator",
                "question": "Inspect metrics",
                "evidence_ids": [],
            },
            {
                "task_id": "logs",
                "role": "logs_trace_investigator",
                "question": "Inspect logs and traces",
                "evidence_ids": [],
            },
            {
                "task_id": "changes",
                "role": "change_investigator",
                "question": "Inspect changes",
                "evidence_ids": [],
            },
        ]
    }


def test_deepseek_model_requests_and_validates_json_output(monkeypatch) -> None:
    captured: dict = {}

    def fake_post(url: str, **kwargs) -> httpx.Response:
        captured.update({"url": url, **kwargs})
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": json.dumps(plan_payload())},
                    }
                ],
                "usage": {"total_tokens": 123},
            },
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    model = DeepSeekRcaModel(
        ControlPlaneSettings(deepseek_api_key="test-key", deepseek_model="test-model")
    )

    plan = model.plan({"id": "incident-1"}, [])

    assert {task.role for task in plan.tasks} == set(InvestigatorRole)
    assert captured["json"]["response_format"] == {"type": "json_object"}
    assert captured["json"]["thinking"] == {"type": "disabled"}
    assert model.call_count == 1
    assert model.total_tokens == 123


def test_deepseek_model_fails_closed_without_api_key() -> None:
    model = DeepSeekRcaModel(ControlPlaneSettings(deepseek_api_key=None))

    with pytest.raises(RcaModelError, match="not configured"):
        model.validate_configuration()

    with pytest.raises(RcaModelError, match="not configured"):
        model.plan({"id": "incident-1"}, [])
