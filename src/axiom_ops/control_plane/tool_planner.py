"""Bounded LLM proposal layer for diagnostic tool collection."""

from __future__ import annotations

from typing import Any, Protocol

from axiom_ops.control_plane.models import ToolSelectionPlan


class ToolPlanner(Protocol):
    def plan_tools(
        self, incident: dict[str, Any], evidence_catalog: list[dict[str, Any]]
    ) -> ToolSelectionPlan: ...
