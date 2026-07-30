"""Thin stdio MCP client adapter for LangGraph nodes and other Agent runtimes."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import os
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


@asynccontextmanager
async def axiomops_mcp_session(
    python_executable: str,
    project_root: Path,
) -> AsyncIterator[ClientSession]:
    """Start the local AxiomOps MCP server and return an initialized client session."""
    environment = os.environ.copy()
    source_root = str(project_root / "src")
    environment["PYTHONPATH"] = os.pathsep.join(
        filter(None, [source_root, environment.get("PYTHONPATH")])
    )
    parameters = StdioServerParameters(
        command=python_executable,
        args=["-m", "axiom_ops.mcp.server"],
        cwd=str(project_root),
        env=environment,
    )
    async with stdio_client(parameters) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            yield session


async def call_axiomops_tool(
    session: ClientSession,
    name: str,
    arguments: dict[str, Any],
) -> Any:
    """Call a named MCP tool; schema validation remains enforced server-side."""
    return await session.call_tool(name, arguments)
