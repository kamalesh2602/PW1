from threading import RLock
from app.models.trace import TraceExecution
from app.services.trace_store.base_store import TraceStore


class InMemoryTraceStore(TraceStore):
    """Thread-safe MVP store; replaceable without changing routes/services."""
    def __init__(self) -> None:
        self._executions: dict[str, TraceExecution] = {}
        self._lock = RLock()

    def save_execution(self, execution: TraceExecution) -> None:
        with self._lock:
            self._executions[execution.execution_id] = execution

    def get_execution(self, execution_id: str) -> TraceExecution | None:
        with self._lock:
            return self._executions.get(execution_id)

    def delete_execution(self, execution_id: str) -> bool:
        with self._lock:
            return self._executions.pop(execution_id, None) is not None
