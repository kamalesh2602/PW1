import os

from fastapi import HTTPException
from app.models.trace import TraceExecution
from app.services.trace_store.base_store import TraceStore


class TraceQueryService:
    def __init__(self, store: TraceStore):
        self.store = store
        self.max_source_radius = int(os.getenv("TRACE_MAX_SOURCE_RADIUS", "50"))
        self.max_query_events = int(os.getenv("TRACE_MAX_QUERY_EVENTS", "500"))

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

    def frame_variables(self, execution_id: str, frame_id: int):
        for frame in self.stack(execution_id):
            if frame.frame_id == frame_id:
                return frame.variables
        raise HTTPException(404, "Stack frame not found")

    def source(self, execution_id: str, file: str, line: int, radius: int = 3):
        if radius < 0 or radius > self.max_source_radius:
            raise HTTPException(422, f"radius must be between 0 and {self.max_source_radius}")
        source = self.execution(execution_id).source_files.get(file)
        if source is None:
            raise HTTPException(404, "Source file not found")
        lines = source.splitlines()
        if line < 1 or line > len(lines):
            raise HTTPException(404, "Source line not found")
        start, end = max(1, line - radius), min(len(lines), line + radius)
        return {"file": file, "start_line": start, "end_line": end,
                "content": "\n".join(f"{n} | {lines[n - 1]}" for n in range(start, end + 1))}

    def path(self, execution_id: str, *, before_event: int | None = None,
             after_event: int | None = None, max_events: int = 100):
        if max_events < 1:
            raise HTTPException(422, "max_events must be at least 1")
        events = self.execution(execution_id).events
        filtered = [event for event in events if (after_event is None or event.event_id >= after_event)
                    and (before_event is None or event.event_id <= before_event)]
        return filtered[:min(max_events, self.max_query_events)]

    def search(self, execution_id: str, filters: dict):
        max_results = filters.get("max_results", 100)
        if not isinstance(max_results, int) or isinstance(max_results, bool) or max_results < 1:
            raise HTTPException(422, "max_results must be a positive integer")
        events = self.execution(execution_id).events

        def matches(event):
            if filters.get("event_type") and event.event_type != filters["event_type"]: return False
            if filters.get("function") and event.function != filters["function"]: return False
            if filters.get("file") and event.file != filters["file"]: return False
            if filters.get("exception_type") and (not event.exception or event.exception.type != filters["exception_type"]): return False
            if filters.get("line_start") is not None and (event.line is None or event.line < filters["line_start"]): return False
            if filters.get("line_end") is not None and (event.line is None or event.line > filters["line_end"]): return False
            variable = filters.get("variable")
            return not variable or variable in event.variables or any(variable in frame.variables for frame in event.stack)

        return [event for event in events if matches(event)][:min(max_results, self.max_query_events)]
