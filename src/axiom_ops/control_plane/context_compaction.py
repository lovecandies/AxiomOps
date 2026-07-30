import json
from dataclasses import dataclass
from typing import Any


class ContextBudgetError(Exception):
    pass


@dataclass(frozen=True)
class CompactedContext:
    capsules: list[dict[str, Any]]
    original_bytes: int
    compressed_bytes: int


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _bounded_text(value: Any, limit: int) -> str:
    text = _json(value)
    if len(text) <= limit:
        return text
    marker = f"...<truncated:{len(text) - limit}>..."
    available = max(0, limit - len(marker))
    head = available // 2
    return text[:head] + marker + text[-(available - head) :]


def _shrink_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    marker = "...<context-budget>..."
    available = max(0, limit - len(marker))
    head = available // 2
    return text[:head] + marker + text[-(available - head) :]


def _relevant_content(kind: str, content: dict[str, Any]) -> Any:
    if kind == "METRIC_SNAPSHOT":
        data = content.get("data", {})
        response = data.get("response", {}) if isinstance(data, dict) else {}
        return {
            "tool_name": content.get("tool_name"),
            "input": content.get("input"),
            "duration_ms": content.get("duration_ms"),
            "query": data.get("query") if isinstance(data, dict) else None,
            "result": response.get("data", {}).get("result", [])
            if isinstance(response, dict)
            else [],
        }
    if kind == "SERVICE_HEALTH":
        return {
            "tool_name": content.get("tool_name"),
            "input": content.get("input"),
            "duration_ms": content.get("duration_ms"),
            "data": content.get("data"),
        }
    if kind in {"TRACE_SNAPSHOT", "CHANGE_EVENT", "FAULT_STATE", "ORDER_FLOW_PROBE"}:
        return {
            "tool_name": content.get("tool_name"),
            "input": content.get("input"),
            "duration_ms": content.get("duration_ms"),
            "data": content.get("data"),
        }
    return content


def compact_evidence(
    evidence: list[dict[str, Any]],
    total_chars: int,
    per_evidence_chars: int,
) -> CompactedContext:
    original_bytes = sum(
        len(_json(item["content"]).encode("utf-8")) for item in evidence
    )
    capsules = [
        {
            "id": item["id"],
            "kind": item["kind"],
            "source": item["source"],
            "observed_at": item["observed_at"],
            "content_sha256": item["content_sha256"],
            "content": _bounded_text(
                _relevant_content(item["kind"], item["content"]),
                per_evidence_chars,
            ),
        }
        for item in evidence
    ]
    while len(_json(capsules)) > total_chars:
        candidate = max(capsules, key=lambda item: len(item["content"]), default=None)
        if candidate is None or len(candidate["content"]) <= 32:
            raise ContextBudgetError("context budget is too small for Evidence metadata")
        candidate["content"] = _shrink_text(
            candidate["content"], len(candidate["content"]) - 32
        )
    compressed_bytes = len(_json(capsules).encode("utf-8"))
    return CompactedContext(capsules, original_bytes, compressed_bytes)
