from fastapi import HTTPException
from app.models.trace import TraceExecution
from app.services.trace_store.base_store import TraceStore


class TraceQueryService:
    def __init__(self, store: TraceStore): self.store = store
    def execution(self, execution_id: str) -> TraceExecution:
        value = self.store.get_execution(execution_id)
        if not value: raise HTTPException(404, "Execution trace not found")
        return value
    def error(self, execution_id: str):
        trace = self.execution(execution_id)
        event = next((e for e in reversed(trace.events) if e.exception), None)
        if not event: raise HTTPException(404, "No error information is available")
        return {"event_id": event.event_id, "error_type": event.exception.type, "message": event.exception.message, "file": event.file, "line": event.line, "function": event.function}
    def stack(self, execution_id: str):
        trace = self.execution(execution_id)
        event = next((e for e in reversed(trace.events) if e.stack), None)
        return event.stack if event else []
    def event(self, execution_id: str, event_id: int):
        event = next((e for e in self.execution(execution_id).events if e.event_id == event_id), None)
        if not event: raise HTTPException(404, "Trace event not found")
        return event
