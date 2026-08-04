"""Shared structured result contract for OpenMCP tools.

Every structured tool returns the same JSON shape while also including a
Markdown text block for MCP clients that only render traditional tool content.
"""

from typing import Annotated, Any, Dict, List, Optional

from mcp.types import CallToolResult, TextContent
from pydantic import BaseModel, Field


class SourceReference(BaseModel):
    """A canonical source used to produce a tool result."""

    title: str
    url: str
    dataset_id: Optional[str] = None
    resource_id: Optional[str] = None


class ToolErrorInfo(BaseModel):
    """A stable, actionable error payload for clients and tests."""

    code: str
    message: str
    retryable: bool = False
    recovery: Optional[str] = None


class ToolResult(BaseModel):
    """Common output schema used by OpenMCP discovery and query tools."""

    datasets: List[Dict[str, Any]] = Field(default_factory=list)
    columns: List[Dict[str, Any]] = Field(default_factory=list)
    rows: List[Dict[str, Any]] = Field(default_factory=list)
    sources: List[SourceReference] = Field(default_factory=list)
    query: Dict[str, Any] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
    error: Optional[ToolErrorInfo] = None


# Annotating CallToolResult with the Pydantic model makes FastMCP publish an
# outputSchema while still allowing us to supply human-readable text content.
StructuredToolResult = Annotated[CallToolResult, ToolResult]


def make_tool_result(
    markdown: str,
    *,
    datasets: Optional[List[Dict[str, Any]]] = None,
    columns: Optional[List[Dict[str, Any]]] = None,
    rows: Optional[List[Dict[str, Any]]] = None,
    sources: Optional[List[SourceReference]] = None,
    query: Optional[Dict[str, Any]] = None,
    warnings: Optional[List[str]] = None,
    error: Optional[ToolErrorInfo] = None,
) -> CallToolResult:
    """Build a validated MCP result with structured and Markdown content."""

    payload = ToolResult(
        datasets=datasets or [],
        columns=columns or [],
        rows=rows or [],
        sources=sources or [],
        query=query or {},
        warnings=warnings or [],
        error=error,
    )
    return CallToolResult(
        content=[TextContent(type="text", text=markdown)],
        structuredContent=payload.model_dump(mode="json"),
        isError=error is not None,
    )


def make_error_result(
    message: str,
    *,
    code: str,
    query: Optional[Dict[str, Any]] = None,
    retryable: bool = False,
    recovery: Optional[str] = None,
    warnings: Optional[List[str]] = None,
) -> CallToolResult:
    """Build a consistent protocol-level tool error with recovery guidance."""

    markdown = f"Error: {message}"
    if recovery:
        markdown += f"\n\nRecovery: {recovery}"
    return make_tool_result(
        markdown,
        query=query,
        warnings=warnings,
        error=ToolErrorInfo(
            code=code,
            message=message,
            retryable=retryable,
            recovery=recovery,
        ),
    )
