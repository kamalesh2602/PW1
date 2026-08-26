from typing import Optional
from fastapi import APIRouter, Query
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
    return queries.frame_variables(execution_id, frame_id)

@router.get("/{execution_id}/source")
def get_source(execution_id: str, file: str, line: int, radius: int = Query(3, ge=0)):
    return queries.source(execution_id, file, line, radius)

@router.get("/{execution_id}/path")
def get_path(execution_id: str, before_event: Optional[int] = None, after_event: Optional[int] = None, max_events: int = Query(100, ge=1)):
    return queries.path(execution_id, before_event=before_event, after_event=after_event, max_events=max_events)

@router.get("/{execution_id}/events/{event_id}")
def get_event(execution_id: str, event_id: int): return queries.event(execution_id, event_id)

@router.post("/{execution_id}/search")
def search(execution_id: str, filters: dict):
    return queries.search(execution_id, filters)
