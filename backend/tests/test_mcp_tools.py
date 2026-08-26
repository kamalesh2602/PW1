import asyncio
from datetime import datetime, timezone

from app.mcp import server
from app.models.trace import StackFrame, TraceEvent, TraceException, TraceExecution
from app.routes.traces import store


EXECUTION_ID = "mcp-tool-test"


def setup_module():
    store.save_execution(TraceExecution(
        execution_id=EXECUTION_ID, language="python", status="runtime_error",
        started_at=datetime.now(timezone.utc), duration=0.01,
        source_files={"script.py": "def divide(a, b):\n    return a / b\n\ndef process():\n    return divide(10, 0)\n\nprocess()"},
        events=[
            TraceEvent(event_id=1, event_type="function_call", language="python", file="script.py", line=4, function="process"),
            TraceEvent(event_id=2, event_type="function_call", language="python", file="script.py", line=2, function="divide"),
            TraceEvent(event_id=3, event_type="exception", language="python", file="script.py", line=2, function="divide",
                variables={"a": 10, "b": 0}, exception=TraceException(type="ZeroDivisionError", message="division by zero"),
                stack=[
                    StackFrame(frame_id=0, function="divide", file="script.py", line=2, variables={"a": 10, "b": 0}),
                    StackFrame(frame_id=1, function="process", file="script.py", line=4, variables={}),
                ]),
        ], total_events_captured=3,
    ))


def test_mcp_tools_return_selective_runtime_context():
    tool_names = {tool.name for tool in asyncio.run(server.mcp.list_tools())}
    assert tool_names == {"get_error_context", "get_stack_trace", "get_frame_variables", "get_source_context",
                          "get_execution_path", "get_event", "search_trace"}
    assert server.get_error_context(EXECUTION_ID)["error_type"] == "ZeroDivisionError"
    assert server.get_stack_trace(EXECUTION_ID)[0]["function"] == "divide"
    assert server.get_frame_variables(EXECUTION_ID, 0) == {"a": 10, "b": 0}
    source = server.get_source_context(EXECUTION_ID, "script.py", 2, 1)
    assert source["start_line"] == 1 and source["end_line"] == 3
    path = server.get_execution_path(EXECUTION_ID, max_events=2)
    assert len(path) == 2 and "variables" not in path[0]
    assert server.get_event(EXECUTION_ID, 3)["exception"]["type"] == "ZeroDivisionError"
    assert server.search_trace(EXECUTION_ID, function="divide", variable="b")[0]["event_id"] == 3


def test_mcp_tools_return_safe_errors_for_invalid_ids():
    assert server.get_error_context("missing")["error"]["code"] == "not_found"
    assert server.get_frame_variables(EXECUTION_ID, 99)["error"]["code"] == "not_found"
    assert server.get_event(EXECUTION_ID, 99)["error"]["code"] == "not_found"
    assert server.get_source_context(EXECUTION_ID, "script.py", 99)["error"]["code"] == "not_found"
    assert server.search_trace(EXECUTION_ID, max_results=0)["error"]["code"] == "invalid_request"
