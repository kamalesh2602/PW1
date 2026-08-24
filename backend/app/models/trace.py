from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


class TraceException(BaseModel):
    type: str
    message: str = ""


class StackFrame(BaseModel):
    frame_id: int
    function: str
    file: str
    line: Optional[int] = None
    variables: dict[str, Any] = Field(default_factory=dict)


class TraceEvent(BaseModel):
    event_id: int
    event_type: str
    language: str
    file: Optional[str] = None
    line: Optional[int] = None
    function: Optional[str] = None
    timestamp: float = 0.0
    stack: list[StackFrame] = Field(default_factory=list)
    variables: dict[str, Any] = Field(default_factory=dict)
    exception: Optional[TraceException] = None


class TraceExecution(BaseModel):
    execution_id: str
    language: str
    status: str
    started_at: datetime
    duration: float
    source_files: dict[str, str] = Field(default_factory=dict)
    events: list[TraceEvent] = Field(default_factory=list)
    error_summary: Optional[TraceException] = None
    truncated: bool = False
    total_events_captured: int = 0
