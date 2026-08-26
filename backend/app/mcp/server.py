"""Local stdio MCP server exposing read-only trace-query tools.

Start from ``backend`` with ``python -m app.mcp.server``.
"""
from typing import Any

from fastapi import HTTPException
from mcp.server.mcpserver import MCPServer

from app.routes.traces import queries
from app.services.mcp_telemetry import record_tool_call


mcp = MCPServer(
    "runtime-debugging-server",
    title="Runtime Debugging Server",
    description="Read-only, selective runtime trace queries for local debugging.",
)


def _error_response(error: HTTPException) -> dict[str, Any]:
    status = error.status_code
    code = "not_found" if status == 404 else "invalid_request" if status == 422 else "trace_unavailable"
    return {"error": {"code": code, "message": str(error.detail)}}


def _call(tool_name: str, execution_id: str, operation) -> Any:
    def run():
        try:
            return operation()
        except HTTPException as error:
            return _error_response(error)
        except (TypeError, ValueError):
            return {"error": {"code": "invalid_request", "message": "Malformed tool parameters"}}
    return record_tool_call(tool_name, execution_id, run)


def _event_summary(event) -> dict[str, Any]:
    return {"event_id": event.event_id, "event_type": event.event_type,
            "function": event.function, "file": event.file, "line": event.line}


@mcp.tool(description="Retrieve the most relevant runtime error for an execution. Use this first to identify a failure without fetching the complete trace.")
def get_error_context(execution_id: str) -> dict[str, Any]:
    return _call("get_error_context", execution_id, lambda: queries.error(execution_id))


@mcp.tool(description="Retrieve the captured stack frames for an execution. Use this to understand the failing call chain without retrieving execution history.")
def get_stack_trace(execution_id: str) -> list[dict[str, Any]] | dict[str, Any]:
    return _call("get_stack_trace", execution_id,
                 lambda: [frame.model_dump(exclude={"variables"}) for frame in queries.stack(execution_id)])


@mcp.tool(description="Retrieve local variables for one stack frame. Use this for targeted runtime state inspection; values use the trace serializer's existing limits.")
def get_frame_variables(execution_id: str, frame_id: int) -> dict[str, Any]:
    return _call("get_frame_variables", execution_id, lambda: queries.frame_variables(execution_id, frame_id))


@mcp.tool(description="Retrieve a small source region around one recorded location. This returns only the requested lines, never the whole file by default.")
def get_source_context(execution_id: str, file: str, line: int, radius: int = 3) -> dict[str, Any]:
    return _call("get_source_context", execution_id, lambda: queries.source(execution_id, file, line, radius))


@mcp.tool(description="Retrieve a bounded, concise execution path. Use it to inspect control flow while avoiding a full event dump.")
def get_execution_path(execution_id: str, max_events: int = 50) -> list[dict[str, Any]] | dict[str, Any]:
    return _call("get_execution_path", execution_id,
                 lambda: [_event_summary(event) for event in queries.path(execution_id, max_events=max_events)])


@mcp.tool(description="Retrieve one detailed runtime event by ID, including its captured variables and exception details when present.")
def get_event(execution_id: str, event_id: int) -> dict[str, Any]:
    return _call("get_event", execution_id, lambda: queries.event(execution_id, event_id).model_dump())


@mcp.tool(description="Search trace events with optional event type, function, file, exception type, line range, or variable filters. Results are bounded and concise.")
def search_trace(execution_id: str, event_type: str | None = None, function: str | None = None,
                 variable: str | None = None, file: str | None = None,
                 exception_type: str | None = None, line_start: int | None = None,
                 line_end: int | None = None, max_results: int = 20) -> list[dict[str, Any]] | dict[str, Any]:
    filters = {key: value for key, value in {
        "event_type": event_type, "function": function, "variable": variable, "file": file,
        "exception_type": exception_type, "line_start": line_start, "line_end": line_end,
        "max_results": max_results,
    }.items() if value is not None}
    return _call("search_trace", execution_id,
                 lambda: [_event_summary(event) for event in queries.search(execution_id, filters)])


if __name__ == "__main__":
    mcp.run(transport="stdio")
