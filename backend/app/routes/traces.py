import os
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from app.services.trace_query_service import TraceQueryService
from app.services.trace_store.memory_store import InMemoryTraceStore

store = InMemoryTraceStore()
queries = TraceQueryService(store)
router = APIRouter(prefix="/executions", tags=["traces"])

@router.get("/{execution_id}")
def get_execution(execution_id: str):
    trace = queries.execution(execution_id)
    return {"execution_id": trace.execution_id, "language": trace.language, "status": trace.status, "duration": trace.duration, "truncated": trace.truncated, "total_events_captured": trace.total_events_captured}

@router.get("/{execution_id}/error")
def get_error(execution_id: str): return queries.error(execution_id)

@router.get("/{execution_id}/stack")
def get_stack(execution_id: str): return queries.stack(execution_id)

@router.get("/{execution_id}/frames/{frame_id}/variables")
def get_variables(execution_id: str, frame_id: int):
    for frame in queries.stack(execution_id):
        if frame.frame_id == frame_id: return frame.variables
    raise HTTPException(404, "Stack frame not found")

MAX_SOURCE_RADIUS = int(os.getenv("TRACE_MAX_SOURCE_RADIUS", "50"))
MAX_QUERY_EVENTS = int(os.getenv("TRACE_MAX_QUERY_EVENTS", "500"))

@router.get("/{execution_id}/source")
def get_source(execution_id: str, file: str, line: int, radius: int = Query(3, ge=0, le=MAX_SOURCE_RADIUS)):
    source = queries.execution(execution_id).source_files.get(file)
    if source is None: raise HTTPException(404, "Source file not found")
    lines = source.splitlines()
    start, end = max(1, line-radius), min(len(lines), line+radius)
    return {"file": file, "start_line": start, "end_line": end, "content": "\n".join(f"{n} | {lines[n-1]}" for n in range(start, end+1))}

@router.get("/{execution_id}/path")
def get_path(execution_id: str, before_event: Optional[int] = None, after_event: Optional[int] = None, max_events: int = Query(100, ge=1, le=MAX_QUERY_EVENTS)):
    events = queries.execution(execution_id).events
    events = [e for e in events if (after_event is None or e.event_id >= after_event) and (before_event is None or e.event_id <= before_event)]
    return events[:max_events]

@router.get("/{execution_id}/events/{event_id}")
def get_event(execution_id: str, event_id: int): return queries.event(execution_id, event_id)

@router.post("/{execution_id}/search")
def search(execution_id: str, filters: dict):
    events = queries.execution(execution_id).events
    def matches(event):
        if filters.get("event_type") and event.event_type != filters["event_type"]: return False
        if filters.get("function") and event.function != filters["function"]: return False
        if filters.get("file") and event.file != filters["file"]: return False
        if filters.get("exception_type") and (not event.exception or event.exception.type != filters["exception_type"]): return False
        if filters.get("line_start") and (event.line is None or event.line < filters["line_start"]): return False
        if filters.get("line_end") and (event.line is None or event.line > filters["line_end"]): return False
        variable = filters.get("variable")
        return not variable or variable in event.variables or any(variable in frame.variables for frame in event.stack)
    return [event for event in events if matches(event)][:min(int(filters.get("max_results", 100)), MAX_QUERY_EVENTS)]
