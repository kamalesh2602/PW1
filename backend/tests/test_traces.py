from app.models.execution import ExecutionLanguage, ExecutionResponse, ExecutionStatus
from app.services.tracing import TraceBuilder
from app.services.trace_store.memory_store import InMemoryTraceStore
from app.services.trace_query_service import TraceQueryService


def test_python_artifact_is_queryable():
    artifact = {"events": [{
        "event_id": 1, "event_type": "exception", "language": "python",
        "file": "script.py", "line": 2, "function": "divide",
        "exception": {"type": "ZeroDivisionError", "message": "division by zero"},
        "stack": [{"frame_id": 0, "function": "divide", "file": "script.py", "line": 2, "variables": {"a": 10, "b": 0}}],
    }]}
    response = ExecutionResponse(status=ExecutionStatus.RUNTIME_ERROR, language=ExecutionLanguage.PYTHON, stderr="Traceback\n  File \"script.py\", line 2\nZeroDivisionError: division by zero", trace_artifact=artifact)
    trace = TraceBuilder().build("test-id", "python", "def divide(a,b):\n return a/b", response)
    store = InMemoryTraceStore(); store.save_execution(trace)
    service = TraceQueryService(store)
    assert service.error("test-id")["error_type"] == "ZeroDivisionError"
    assert service.stack("test-id")[0].variables == {"a": 10, "b": 0}


def test_java_compilation_error_is_not_a_runtime_trace():
    response = ExecutionResponse(status=ExecutionStatus.COMPILE_ERROR, language=ExecutionLanguage.JAVA, stderr="Main.java:3: error: ';' expected")
    trace = TraceBuilder().build("compile-id", "java", "public class Main {}", response)
    assert trace.events[-1].event_type == "compilation_error"
    assert trace.events[-1].line == 3
